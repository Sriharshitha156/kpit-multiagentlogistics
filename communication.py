"""
communication.py - the simulated network: Message and MessageBus.

Agents NEVER read each other's variables. The only way one agent learns anything
about another is through a Message delivered by this bus.
The bus can delay and lose messages, and it counts all traffic (our
"communication overhead" metric).
"""

import random
from collections import deque

import config

# Message types used by task allocation, delivery reporting and failure recovery.
TASK_REQUEST = "TASK_REQUEST"          # order desk -> everyone: "who wants this delivery?"
TASK_BID = "TASK_BID"                  # agent -> everyone: "I can do it at this cost"
TASK_ACCEPT = "TASK_ACCEPT"            # winner -> everyone: "I own this task"
DELIVERY_COMPLETE = "DELIVERY_COMPLETE"
TASK_REASSIGN = "TASK_REASSIGN"        # peer announces a new auction epoch for orphaned work
TASK_CANCEL = "TASK_CANCEL"            # order desk withdraws an unassigned task
HEARTBEAT = "HEARTBEAT"                # agent reports that it is alive
AGENT_FAILURE = "AGENT_FAILURE"        # peer reports its failure suspicion
SYNC_STATE = "SYNC_STATE"                # peer shares its task ledger after reconnection
COMMUNICATION_PARTITION = "COMMUNICATION_PARTITION"
COMMUNICATION_RESTORED = "COMMUNICATION_RESTORED"
SYNC_COMPLETE = "SYNC_COMPLETE"
SYNC_CONFLICT = "SYNC_CONFLICT"

BROADCAST = "BROADCAST"                # receiver value meaning "send to everyone"
DESK = "DESK"                          # sender id of the order desk (it is not an agent)


def describe_message(msg_type, sender_id, payload):
    """One readable line for the live message feed, e.g. 'A3 -> ALL  TASK_BID  #7 cost 14.2'."""
    sender = sender_id if sender_id == DESK else "A%s" % sender_id
    if msg_type == TASK_REQUEST:
        detail = "#%d priority %d" % (payload["task"].task_id, payload["task"].priority)
    elif msg_type == TASK_BID:
        detail = "#%d cost %.1f" % (payload["task_id"], payload["cost"])
    elif msg_type == TASK_ACCEPT:
        detail = "#%d (epoch %d)" % (payload["task_id"], payload["epoch"])
    elif msg_type == TASK_REASSIGN:
        detail = "#%d epoch %d (%s)" % (payload["task"].task_id, payload["epoch"], payload["reason"])
    elif msg_type == TASK_CANCEL:
        detail = "#%d" % payload["task_id"]
    elif msg_type == AGENT_FAILURE:
        detail = "A%d declared dead" % payload["failed_id"]
    elif msg_type == DELIVERY_COMPLETE:
        detail = "#%d" % payload["task_id"]
    else:
        detail = ""
    return "%s -> ALL  %s  %s" % (sender, msg_type, detail)


def explain_message(msg_type, sender_id, payload):
    """Plain-language event description, retaining the technical type separately."""
    sender = "Order desk" if sender_id == DESK else "Vehicle A%d" % sender_id
    if msg_type == TASK_REQUEST:
        task = payload["task"]
        priority = {1: "low", 2: "medium", 3: "high"}.get(task.priority, "unknown")
        return "New Order #%d announced (%s priority)" % (task.task_id, priority)
    if msg_type == TASK_BID:
        return "Vehicle A%d bid on Order #%d — score %.1f" % (
            sender_id, payload["task_id"], payload["cost"])
    if msg_type == TASK_ACCEPT:
        return "Vehicle A%d won Order #%d — bid score %.1f" % (
            sender_id, payload["task_id"], payload["cost"])
    if msg_type == TASK_REASSIGN:
        task = payload["task"]
        return "Order #%d reopened for bids (%s)" % (task.task_id, payload["reason"].lower().replace("_", " "))
    if msg_type == TASK_CANCEL:
        return "Order #%d cancelled before assignment" % payload["task_id"]
    if msg_type == DELIVERY_COMPLETE:
        return "Vehicle A%d delivered Order #%d" % (sender_id, payload["task_id"])
    if msg_type == AGENT_FAILURE:
        return "Vehicle A%d suspects A%d has failed" % (sender_id, payload["failed_id"])
    if msg_type == HEARTBEAT:
        return "Vehicle A%d heartbeat received" % sender_id
    if msg_type == SYNC_STATE:
        return "Vehicle A%d shared its task ledger after reconnection" % sender_id
    if msg_type == "VEHICLE_FAILED":
        affected = payload.get("affected_task_ids", [])
        if affected:
            orders = ", ".join("#%d" % task_id for task_id in affected)
            return "Vehicle A%d failed; Order%s %s need recovery" % (
                payload["agent_id"], "s" if len(affected) != 1 else "", orders)
        return "Vehicle A%d failed; it had no active orders" % payload["agent_id"]
    if msg_type == "ROAD_BLOCKED":
        x, y = payload["cell"]
        return "Road blocked at (%d, %d); %d active route(s) need rerouting" % (
            x, y, payload.get("routes_invalidated", 0))
    if msg_type == "REROUTE_SUCCESS":
        return "Vehicle A%d found an alternate A* route" % payload["agent_id"]
    if msg_type == COMMUNICATION_PARTITION:
        return "Communication partition: groups are operating locally"
    if msg_type == COMMUNICATION_RESTORED:
        return "Communication restored: vehicles are synchronizing"
    if msg_type == SYNC_COMPLETE:
        return "Vehicle ledgers synchronized"
    if msg_type == SYNC_CONFLICT:
        return "Order #%d ownership conflict resolved: A%d retained the task" % (
            payload["task_id"], payload["owner_id"])
    return "%s sent %s" % (sender, msg_type.replace("_", " ").lower())


class Message:
    """One message. `payload` is a dictionary with the content."""

    def __init__(self, msg_id, msg_type, sender_id, receiver_id, tick_sent, tick_deliver, payload):
        self.msg_id = msg_id
        self.msg_type = msg_type
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.tick_sent = tick_sent
        self.tick_deliver = tick_deliver
        self.payload = payload


class MessageBus:
    """Carries messages between agents, with delay, optional loss and counting."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)         # separate generator, so loss never changes the map
        self.alive_ids = []                    # agents that can currently receive messages
        self.pending = []                      # messages in flight
        self.inboxes = {}                      # agent_id -> list of delivered messages
        self.next_msg_id = 1
        self.messages_sent = 0                 # transmissions (a broadcast counts once)
        self.messages_delivered = 0            # arrivals (a broadcast counts once per receiver)
        self.messages_lost = 0
        self.sent_by_type = {}
        self.log = deque(maxlen=300)           # recent transmissions, for the live message feed
        self.auction_history = []              # audit records reconstructed from actual transmissions
        self._auction_by_key = {}
        self.partition_group_by_agent = None
        self.messages_partitioned = 0
        self.communication_partitions = 0
        self.network_restorations = 0
        self.synchronizations_completed = 0
        self.sync_conflicts = 0
        self.sync_generation = 0
        self.sync_expected = set()
        self.sync_received = {}
        self.sync_complete = False
        self._system_event_keys = set()

    @property
    def partitioned(self):
        return self.partition_group_by_agent is not None

    def set_partition(self, groups, tick=0):
        """Drop agent-to-agent messages that cross the supplied network groups."""
        groups = [set(group) for group in groups if group]
        flattened = [agent_id for group in groups for agent_id in group]
        if len(groups) < 2 or len(flattened) != len(set(flattened)) or set(flattened) != set(self.alive_ids):
            raise ValueError("partition groups must divide all living agents into at least two groups")
        self.partition_group_by_agent = {
            agent_id: group_index for group_index, group in enumerate(groups) for agent_id in group
        }
        self.sync_expected.clear()
        self.sync_received.clear()
        self.sync_complete = False
        self.communication_partitions += 1
        self.note_event(COMMUNICATION_PARTITION, {"groups": [sorted(group) for group in groups]}, tick)

    def restore_network(self, tick=0):
        """Restore cross-group links and prepare to observe peer ledger exchange."""
        if not self.partitioned:
            return False
        self.partition_group_by_agent = None
        self.sync_generation += 1
        self.network_restorations += 1
        self.sync_expected = set(self.alive_ids)
        self.sync_received = {agent_id: set() for agent_id in self.alive_ids}
        self.sync_complete = len(self.sync_expected) <= 1
        self.note_event(COMMUNICATION_RESTORED, {"generation": self.sync_generation}, tick)
        if self.sync_complete:
            self.synchronizations_completed += 1
            self.note_event(SYNC_COMPLETE, {"generation": self.sync_generation}, tick)
        return True

    def note_sync_processed(self, receiver_id, sender_id, tick):
        if self.sync_complete or receiver_id not in self.sync_expected or sender_id == receiver_id:
            return
        self.sync_received[receiver_id].add(sender_id)
        if all(self.sync_expected - {receiver} <= seen for receiver, seen in self.sync_received.items()):
            self.sync_complete = True
            self.synchronizations_completed += 1
            self.note_event(SYNC_COMPLETE, {"generation": self.sync_generation}, tick)

    def note_event(self, event_type, payload, tick, once_key=None):
        if once_key is not None:
            if once_key in self._system_event_keys:
                return False
            self._system_event_keys.add(once_key)
        if event_type == SYNC_CONFLICT:
            self.sync_conflicts += 1
        self.log.append((tick, event_type, DESK, payload))
        return True

    def _partition_allows(self, sender_id, receiver_id):
        if not self.partitioned or sender_id == DESK:
            return True
        groups = self.partition_group_by_agent
        return groups.get(sender_id) == groups.get(receiver_id)

    def _record_auction_message(self, msg_type, sender_id, payload):
        """Keep a read-only audit trail of auction requests, bids, and claims."""
        if msg_type == TASK_REQUEST:
            task = payload["task"]
            task_id, epoch = task.task_id, payload["epoch"]
        elif msg_type == TASK_REASSIGN:
            task = payload["task"]
            task_id, epoch = task.task_id, payload["epoch"]
        elif msg_type in (TASK_BID, TASK_ACCEPT):
            if "task_id" not in payload or "epoch" not in payload:
                return
            task = None
            task_id, epoch = payload["task_id"], payload["epoch"]
        else:
            return

        key = (task_id, epoch)
        record = self._auction_by_key.get(key)
        if record is None:
            record = {"task_id": task_id, "epoch": epoch, "priority": None,
                      "bids": {}, "bid_details": {}, "accepts": {}}
            self._auction_by_key[key] = record
            self.auction_history.append(record)
        if task is not None:
            record["priority"] = task.priority
        if msg_type == TASK_BID:
            record["bids"][sender_id] = payload["cost"]
            if payload.get("details") is not None:
                record["bid_details"][sender_id] = payload["details"]
        elif msg_type == TASK_ACCEPT:
            record["accepts"][sender_id] = payload["cost"]

    def set_alive(self, agent_ids):
        """Tell the bus which agents are alive (dead agents receive nothing)."""
        self.alive_ids = list(agent_ids)

    def send(self, msg_type, sender_id, receiver_id, tick, payload):
        """Send a message to one agent, or to everybody else with BROADCAST."""
        self.messages_sent += 1
        self.sent_by_type[msg_type] = self.sent_by_type.get(msg_type, 0) + 1
        self.log.append((tick, msg_type, sender_id, payload))
        self._record_auction_message(msg_type, sender_id, payload)
        if receiver_id == BROADCAST:
            receivers = [i for i in self.alive_ids if i != sender_id]
        else:
            receivers = [receiver_id]
        for receiver in receivers:
            if not self._partition_allows(sender_id, receiver):
                self.messages_partitioned += 1
                continue
            if config.LOSS_PROBABILITY > 0 and self.rng.random() < config.LOSS_PROBABILITY:
                self.messages_lost += 1
                continue
            message = Message(self.next_msg_id, msg_type, sender_id, receiver, tick,
                              tick + config.MESSAGE_DELAY, payload)
            self.next_msg_id += 1
            self.pending.append(message)

    def deliver(self, tick):
        """Move every message whose delivery time has come into its receiver's inbox."""
        still_in_flight = []
        for message in self.pending:
            if message.tick_deliver <= tick:
                if self._partition_allows(message.sender_id, message.receiver_id):
                    self.inboxes.setdefault(message.receiver_id, []).append(message)
                    self.messages_delivered += 1
                else:
                    self.messages_partitioned += 1
            else:
                still_in_flight.append(message)
        self.pending = still_in_flight

    def collect(self, agent_id):
        """An agent reads (and empties) its inbox."""
        return self.inboxes.pop(agent_id, [])
