"""Optional localhost UDP transport for inspecting real simulator messages.

The simulation still owns scheduling and agent execution. This bus serializes each
recipient copy and sends it as a UDP datagram over loopback; the default MessageBus
remains the deterministic in-process transport used by experiments.
"""

import json
import socket

import config
from communication import BROADCAST, DESK, Message, MessageBus
from task import TaskInfo


def _pack(value):
    if isinstance(value, TaskInfo):
        return {"__kind__": "TaskInfo", "task_id": value.task_id,
                "pickup": _pack(value.pickup), "destination": _pack(value.destination),
                "priority": value.priority, "created_tick": value.created_tick,
                "deadline_tick": value.deadline_tick}
    if isinstance(value, tuple):
        return {"__kind__": "tuple", "items": [_pack(item) for item in value]}
    if isinstance(value, dict):
        return {key: _pack(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_pack(item) for item in value]
    return value


def _unpack(value):
    if isinstance(value, list):
        return [_unpack(item) for item in value]
    if isinstance(value, dict):
        kind = value.get("__kind__")
        if kind == "tuple":
            return tuple(_unpack(item) for item in value["items"])
        if kind == "TaskInfo":
            return TaskInfo(value["task_id"], _unpack(value["pickup"]),
                            _unpack(value["destination"]), value["priority"], value["created_tick"],
                            value.get("deadline_tick"))
        return {key: _unpack(item) for key, item in value.items()}
    return value


class LocalUdpMessageBus(MessageBus):
    """MessageBus-compatible transport that sends localhost UDP datagrams."""

    def __init__(self, seed=0, agent_ids=()):
        super().__init__(seed)
        self.agent_sockets = {}
        self.desk_socket = self._new_socket()
        for agent_id in agent_ids:
            self.agent_sockets[agent_id] = self._new_socket()
        self.udp_endpoints = {agent_id: sock.getsockname()[1]
                              for agent_id, sock in self.agent_sockets.items()}

    @staticmethod
    def _new_socket():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        sock.setblocking(False)
        return sock

    def send(self, msg_type, sender_id, receiver_id, tick, payload):
        """Serialize one message and send a datagram to each intended recipient."""
        self.messages_sent += 1
        self.sent_by_type[msg_type] = self.sent_by_type.get(msg_type, 0) + 1
        self.log.append((tick, msg_type, sender_id, payload))
        self._record_auction_message(msg_type, sender_id, payload)
        if receiver_id == BROADCAST:
            receivers = [agent_id for agent_id in self.alive_ids if agent_id != sender_id]
        else:
            receivers = [receiver_id]

        sender_socket = self.desk_socket if sender_id == DESK else self.agent_sockets[sender_id]
        for recipient_id in receivers:
            if not self._partition_allows(sender_id, recipient_id):
                self.messages_partitioned += 1
                continue
            if config.LOSS_PROBABILITY > 0 and self.rng.random() < config.LOSS_PROBABILITY:
                self.messages_lost += 1
                continue
            wire = {
                "msg_id": self.next_msg_id,
                "msg_type": msg_type,
                "sender_id": sender_id,
                "receiver_id": recipient_id,
                "tick_sent": tick,
                "tick_deliver": tick + config.MESSAGE_DELAY,
                "payload": _pack(payload),
            }
            packet = json.dumps(wire, separators=(",", ":")).encode("utf-8")
            sender_socket.sendto(packet, self.agent_sockets[recipient_id].getsockname())
            self.next_msg_id += 1

    def deliver(self, tick):
        """Read datagrams from agent sockets and release messages whose tick has come."""
        for receiver_id, sock in self.agent_sockets.items():
            while True:
                try:
                    packet, _ = sock.recvfrom(65535)
                except BlockingIOError:
                    break
                wire = json.loads(packet.decode("utf-8"))
                message = Message(wire["msg_id"], wire["msg_type"], wire["sender_id"],
                                  wire["receiver_id"], wire["tick_sent"], wire["tick_deliver"],
                                  _unpack(wire["payload"]))
                self.pending.append(message)

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

    def close(self):
        """Close all loopback sockets. Safe to call more than once."""
        for sock in [self.desk_socket, *self.agent_sockets.values()]:
            if sock.fileno() >= 0:
                sock.close()
