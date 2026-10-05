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
HEARTBEAT = "HEARTBEAT"                # agent reports that it is alive
AGENT_FAILURE = "AGENT_FAILURE"        # peer reports its failure suspicion

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
    elif msg_type == AGENT_FAILURE:
        detail = "A%d declared dead" % payload["failed_id"]
    elif msg_type == DELIVERY_COMPLETE:
        detail = "#%d" % payload["task_id"]
    else:
        detail = ""
    return "%s -> ALL  %s  %s" % (sender, msg_type, detail)


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
                      "bids": {}, "accepts": {}}
            self._auction_by_key[key] = record
            self.auction_history.append(record)
        if task is not None:
            record["priority"] = task.priority
        if msg_type == TASK_BID:
            record["bids"][sender_id] = payload["cost"]
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
                self.inboxes.setdefault(message.receiver_id, []).append(message)
                self.messages_delivered += 1
            else:
                still_in_flight.append(message)
        self.pending = still_in_flight

    def collect(self, agent_id):
        """An agent reads (and empties) its inbox."""
        return self.inboxes.pop(agent_id, [])
