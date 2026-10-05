"""
agent.py - one autonomous delivery vehicle.

PHASE 7 VERSION: agents can take part in auctions.
  * A new order arrives as a TASK_REQUEST message.
  * Every agent computes its OWN bid cost from its OWN state (compute_bid).
  * Every agent collects the bids it hears and picks the winner with the SAME
    public rule: lowest cost, ties go to the lowest agent ID.
  * The winner announces TASK_ACCEPT. Nobody tells anybody what to do.

Each agent keeps its own copy of a "ledger": who owns which task. It is built
only from messages. Agents never look at the environment's Task objects.

PHASE 8: movement and bid distances now use A* on the agent's OWN copy of the map
(known_obstacles). New obstacles reach the agent as events (perceive_obstacle).

PHASE 9: every agent sends heartbeats and watches its peers. If a peer falls silent,
EVERY agent independently decides it is dead, finds that peer's unfinished tasks in its
OWN ledger, raises their epoch and re-auctions them. No leader is involved.
"""

import config
from communication import (AGENT_FAILURE, BROADCAST, DELIVERY_COMPLETE, HEARTBEAT, SYNC_STATE, TASK_ACCEPT,
                           TASK_BID, TASK_CANCEL, TASK_REASSIGN, TASK_REQUEST, Message)
from pathfinding import astar
from task import TaskInfo

# Agent statuses (same names as in our design document)
IDLE = "IDLE"
GOING_TO_PICKUP = "GOING_TO_PICKUP"
DELIVERING = "DELIVERING"
GOING_TO_CHARGE = "GOING_TO_CHARGE"
CHARGING = "CHARGING"
FAILED = "FAILED"

# Ledger entry statuses
BIDDING = "BIDDING"            # auction open, collecting bids
PROVISIONAL = "PROVISIONAL"    # winner computed, waiting for the winner's TASK_ACCEPT
ASSIGNED = "ASSIGNED"          # winner confirmed
NO_BIDS = "NO_BIDS"            # nobody could take it; will be re-auctioned later
DONE = "DONE"                  # delivered
CANCELLED = "CANCELLED"        # withdrawn before assignment


class Agent:
    """A single vehicle with its own battery, position, task queue and ledger."""

    def __init__(self, agent_id, start_position, bus=None, known_obstacles=None, peer_ids=None, speed=config.AGENT_SPEED):
        self.agent_id = agent_id
        self.position = start_position
        self.battery = float(config.BATTERY_MAX)
        self.speed = speed                  # cells per tick
        self.status = IDLE
        self.bus = bus                      # my "network card" (None for the central baselines)
        self.assigned_task = None           # the TaskInfo I am serving right now
        self.task_queue = []                # TaskInfo objects waiting for their turn
        self.ledger = {}                    # task_id -> dictionary (see _open_auction)
        self.known_obstacles = set(known_obstacles or [])   # my own copy of the map
        self.path = []                      # cells I still have to walk through (from A*)
        self.path_target = None             # the goal that `path` leads to
        self._length_cache = {}             # (start, goal) -> A* length, cleared on map changes
        self.replans = 0                    # how many times I had to compute a new route
        self.route_reroutes = 0             # path was invalidated by a newly blocked road
        self.successful_reroutes = 0
        self._reroute_pending = False
        self.last_heard = {pid: 0 for pid in (peer_ids or [])}   # peer -> last tick I heard from it
        self.peer_info = {}                 # peer -> its last heartbeat (position, carrying, ...)
        self.suspected_dead = set()         # peers I believe have failed
        self.failed_tick = None
        self.wander_target = None           # only used if WANDER_WHEN_IDLE is True
        self.charger_target = None
        self.distance_travelled = 0
        self.energy_used = 0.0
        self.energy_charged = 0.0
        self.fail_reason = None
        # counters used by the metrics
        self.tasks_completed = 0
        self.busy_ticks = 0
        self.alive_ticks = 0

    def is_alive(self):
        return self.status != FAILED

    def is_available(self):
        """Idle with nothing queued (used by baseline B1)."""
        return self.is_alive() and self.status == IDLE and not self.task_queue and self.assigned_task is None

    def fail(self, reason, tick=None):
        """Permanently stop this agent. Reason is 'BATTERY' or 'CLICKED'."""
        self.status = FAILED
        self.fail_reason = reason
        self.failed_tick = tick

    def enqueue_task(self, task_info):
        """Add a task to my queue (called when I win an auction, or by a central dispatcher)."""
        self.task_queue.append(task_info)

    # ---------- map knowledge and distances ----------
    def perceive_obstacle(self, cell):
        """The environment tells me a new cell is blocked."""
        self.known_obstacles.add(cell)
        self._length_cache.clear()
        if cell in self.path:
            self.route_reroutes += 1
            self._reroute_pending = True
            self.path = []                                # forces a new A* route next step

    def path_length(self, start, goal, env):
        """Shortest walking distance from start to goal on MY map, or None if unreachable."""
        key = (start, goal)
        if key not in self._length_cache:
            route = astar(start, goal, self.known_obstacles, env.width, env.height)
            self._length_cache[key] = None if route is None else len(route)
        return self._length_cache[key]

    # ---------- the bid ----------
    def _planned_work(self, task, env):
        """Estimate the route I would actually follow if I also accepted `task`.

        The active task stays first. Remaining jobs use the same priority/age order
        as `_start_next_task`. Return total route distance, final position, and the
        distance travelled before reaching this task's pickup.
        """
        position = self.position
        distance = 0
        distance_to_candidate = None
        if self.assigned_task is not None:
            if self.status == GOING_TO_PICKUP:
                length = self.path_length(position, self.assigned_task.pickup, env)
                if length is None:
                    return None, position, None
                distance += length
                position = self.assigned_task.pickup
            length = self.path_length(position, self.assigned_task.destination, env)
            if length is None:
                return None, position, None
            distance += length
            position = self.assigned_task.destination

        pending = [queued for queued in self.task_queue if queued.task_id != task.task_id]
        pending.append(task)
        pending.sort(key=lambda queued: (-queued.priority, queued.created_tick, queued.task_id))
        for queued in pending:
            to_pickup = self.path_length(position, queued.pickup, env)
            if to_pickup is None:
                return None, position, None
            if queued.task_id == task.task_id:
                distance_to_candidate = distance + to_pickup
            distance += to_pickup
            to_destination = self.path_length(queued.pickup, queued.destination, env)
            if to_destination is None:
                return None, position, None
            distance += to_destination
            position = queued.destination

        return distance, position, distance_to_candidate

    def compute_bid(self, task, env):
        """Return the scalar auction score, or None when I cannot safely bid."""
        details = self.compute_bid_details(task, env)
        return None if details is None else details["cost"]

    def compute_bid_details(self, task, env):
        """
        Return the real score inputs used for a bid, or None if ineligible.

        I do not bid if I am charging, if my queue is full, or if the battery
        cannot cover: everything I already hold + this task + a trip to a charger.
        All distances are A* path lengths on my own map.
        """
        if self.status in (FAILED, CHARGING, GOING_TO_CHARGE):
            return None
        load = len(self.task_queue) + (1 if self.assigned_task is not None else 0)
        if load >= config.MAX_QUEUE:
            return None

        planned_distance, end_position, distance_to_pickup = self._planned_work(task, env)
        delivery = self.path_length(task.pickup, task.destination, env)
        charger_trips = [self.path_length(end_position, c, env) for c in env.chargers]
        charger_trips = [d for d in charger_trips if d is not None]
        if planned_distance is None or distance_to_pickup is None or delivery is None or not charger_trips:
            return None                                   # something is unreachable
        back_to_charger = min(charger_trips)

        energy_needed = (planned_distance + back_to_charger) * config.ENERGY_PER_CELL
        if self.battery < energy_needed * (1 + config.SAFETY_MARGIN):
            return None                                   # battery feasibility check failed

        time_until_pickup = distance_to_pickup / self.speed
        delivery_time = delivery / self.speed
        cost = (config.W_TIME * (config.PRIORITY_FACTOR[task.priority] * time_until_pickup + delivery_time)
                + config.W_LOAD * load)
        return {
            "cost": round(cost, 3),
            "distance_to_pickup": distance_to_pickup,
            "delivery_distance": delivery,
            "pickup_time": time_until_pickup,
            "delivery_time": delivery_time,
            "load": load,
            "priority_factor": config.PRIORITY_FACTOR[task.priority],
            "battery_pct": round(100 * self.battery / config.BATTERY_MAX, 1),
            "energy_required_with_reserve": round(energy_needed * (1 + config.SAFETY_MARGIN), 2),
        }

    # ---------- the agent's "brain": called once per tick ----------
    def update(self, env, tick):
        """Do one tick: read messages, run auctions, then move."""
        if self.status == FAILED:
            return

        self.alive_ticks += 1
        if self.status in (GOING_TO_PICKUP, DELIVERING):
            self.busy_ticks += 1

        if self.bus is not None:
            self._process_messages(env, tick)
            self._detect_failures(env, tick)
            self._run_auction_timers(env, tick)
            self._send_heartbeat(tick)

        if self.status == CHARGING:
            self._charge()
            return

        if self.status == IDLE:
            if self.task_queue:
                self._start_next_task()
            elif self.battery < config.LOW_BATTERY:
                self.charger_target = env.nearest_charger(self.position)
                self.status = GOING_TO_CHARGE

        target = self._current_target(env)
        for _ in range(self.speed):
            if self.position == target:
                break
            self._step_along_path(target, env, tick)
            if self.battery <= 0:
                self.battery = 0
                self.fail("BATTERY", tick)
                return

        self._handle_arrival(env, tick)

    # ---------- auction logic ----------
    def _process_messages(self, env, tick):
        """Read my inbox and react to each message."""
        for message in self.bus.collect(self.agent_id):
            payload = message.payload
            if message.sender_id in self.last_heard:          # any message proves the sender is alive
                self.last_heard[message.sender_id] = tick
                self.suspected_dead.discard(message.sender_id)
            if message.msg_type == TASK_REQUEST:
                self._open_auction(payload["task"], payload["epoch"], env, tick)
            elif message.msg_type == TASK_BID:
                self._on_bid(message)
            elif message.msg_type == TASK_ACCEPT:
                self._on_accept(message)
            elif message.msg_type == DELIVERY_COMPLETE:
                entry = self.ledger.get(payload["task_id"])
                if entry is not None:
                    entry["status"] = DONE
                    entry["completed_tick"] = message.tick_sent
                self._drop_task(payload["task_id"])           # someone already delivered it
            elif message.msg_type == TASK_CANCEL:
                self._on_cancel(payload)
            elif message.msg_type == HEARTBEAT:
                self.peer_info[message.sender_id] = payload
            elif message.msg_type == AGENT_FAILURE:
                failed_id = payload["failed_id"]
                if failed_id != self.agent_id and failed_id not in self.suspected_dead:
                    self._declare_failed(failed_id, env, tick, announce=False)
            elif message.msg_type == TASK_REASSIGN:
                self._on_reassign(payload, env, tick)
            elif message.msg_type == SYNC_STATE:
                self._on_sync_state(message, env, tick)

    def _open_auction(self, task, epoch, env, tick):
        """Start (or restart) an auction for a task and place my own bid if I can."""
        old = self.ledger.get(task.task_id)
        if old is not None and epoch <= old["epoch"]:
            return                                        # old or duplicate announcement
        bids = {}
        my_details = self.compute_bid_details(task, env)
        if my_details is not None:
            my_cost = my_details["cost"]
            bids[self.agent_id] = my_cost
            self.bus.send(TASK_BID, self.agent_id, BROADCAST, tick,
                          {"task_id": task.task_id, "epoch": epoch, "cost": my_cost,
                           "details": my_details})
        self.ledger[task.task_id] = {"task": task, "epoch": epoch, "owner": None, "cost": None,
                                     "status": BIDDING, "bids": bids,
                                     "decide_at": tick + config.BID_WINDOW}

    def _on_bid(self, message):
        """Remember a bid I heard, if it belongs to the auction I currently have open."""
        payload = message.payload
        entry = self.ledger.get(payload["task_id"])
        if entry is not None and entry["status"] == BIDDING and entry["epoch"] == payload["epoch"]:
            entry["bids"][message.sender_id] = payload["cost"]

    def _on_cancel(self, payload):
        """Forget an order the desk withdrew before it was assigned."""
        entry = self.ledger.get(payload["task_id"])
        if entry is None or payload["epoch"] >= entry["epoch"]:
            if entry is None:
                self.ledger[payload["task_id"]] = {
                    "task": None, "epoch": payload["epoch"], "owner": None, "cost": None,
                    "status": CANCELLED, "bids": {},
                }
            else:
                entry["status"] = CANCELLED
                entry["owner"] = None
                self._drop_task(payload["task_id"])

    def broadcast_sync_state(self, tick):
        """Share only this vehicle's ledger after a network partition is lifted."""
        if self.bus is None or not self.is_alive():
            return
        entries = []
        for task_id, entry in self.ledger.items():
            if entry.get("task") is None:
                continue
            entries.append({
                "task": entry["task"], "epoch": entry["epoch"], "owner": entry["owner"],
                "cost": entry["cost"], "status": entry["status"], "bids": dict(entry["bids"]),
                "completed_tick": entry.get("completed_tick"),
                "carrying": (self.assigned_task is not None
                             and self.assigned_task.task_id == task_id and self.status == DELIVERING),
            })
        self.bus.send(SYNC_STATE, self.agent_id, BROADCAST, tick,
                      {"generation": self.bus.sync_generation, "entries": entries})

    def _on_sync_state(self, message, env, tick):
        """Merge peer snapshots deterministically; bids/claims remain agent-local evidence."""
        payload = message.payload
        if payload.get("generation") != self.bus.sync_generation:
            return
        for remote in payload["entries"]:
            task = remote["task"]
            task_id, epoch = task.task_id, remote["epoch"]
            entry = self.ledger.get(task_id)
            if entry is None:
                entry = {"task": task, "epoch": epoch, "owner": None, "cost": None,
                         "status": BIDDING, "bids": {}, "decide_at": tick + 1}
                self.ledger[task_id] = entry
            if epoch < entry["epoch"]:
                continue
            old_owner = entry["owner"]
            old_epoch = entry["epoch"]

            if remote["status"] == DONE:
                entry["task"] = task
                entry["epoch"] = max(entry["epoch"], epoch)
                entry["status"] = DONE
                entry["owner"] = remote["owner"]
                entry["completed_tick"] = remote.get("completed_tick")
                self._drop_task(task_id)
                env.record_delivery(task_id, remote.get("completed_tick") or tick)
            elif remote["status"] == CANCELLED:
                if entry["status"] not in (DONE, ASSIGNED):
                    entry["task"] = task
                    entry["epoch"] = epoch
                    entry["status"] = CANCELLED
                    entry["owner"] = None
                    self._drop_task(task_id)
            elif remote["owner"] is not None:
                if entry["status"] in (DONE, CANCELLED):
                    continue
                if epoch > old_epoch:
                    if entry["owner"] == self.agent_id:
                        self._drop_task(task_id)
                    entry.update({"task": task, "epoch": epoch, "owner": None, "cost": None,
                                  "status": PROVISIONAL, "bids": {}})
                claim = Message(0, TASK_ACCEPT, remote["owner"], self.agent_id, tick, tick,
                                {"task_id": task_id, "epoch": epoch, "cost": remote["cost"]})
                local_carrying = (entry.get("carrying", False)
                                  or (entry["owner"] == self.agent_id and self.assigned_task is not None
                                      and self.assigned_task.task_id == task_id and self.status == DELIVERING))
                remote_carrying = remote.get("carrying", False)
                if remote_carrying and not local_carrying:
                    if entry["owner"] == self.agent_id:
                        self._drop_task(task_id)
                        if self.assigned_task is not None and self.assigned_task.task_id == task_id:
                            self.assigned_task = None
                            self.status = IDLE
                    entry.update({"task": task, "epoch": epoch, "owner": remote["owner"],
                                  "cost": remote["cost"], "status": ASSIGNED, "carrying": True})
                elif local_carrying and not remote_carrying:
                    entry["carrying"] = True
                    continue
                else:
                    self._on_accept(claim)
                    entry["carrying"] = remote_carrying if entry["owner"] == remote["owner"] else local_carrying
                if old_owner == self.agent_id and entry["owner"] != self.agent_id:
                    if self.assigned_task is not None and self.assigned_task.task_id == task_id:
                        self.assigned_task = None
                        self.status = IDLE
                if entry["owner"] == self.agent_id:
                    if (self.assigned_task is None or self.assigned_task.task_id != task_id) and not any(
                            queued.task_id == task_id for queued in self.task_queue):
                        self.enqueue_task(task)
                    env.record_assignment(task_id, self.agent_id, tick,
                                          recovery_approach_distance=self.path_length(self.position, task.pickup, env))
                if old_owner is not None and entry["owner"] != old_owner:
                    self.bus.note_event("SYNC_CONFLICT", {"task_id": task_id, "owner_id": entry["owner"],
                                                           "previous_owner_id": old_owner}, tick,
                                        once_key=("sync-conflict", self.bus.sync_generation, task_id, epoch))
            elif entry["owner"] is None and entry["status"] not in (DONE, CANCELLED):
                if epoch > old_epoch:
                    entry.update({"task": task, "epoch": epoch, "status": BIDDING, "owner": None,
                                  "cost": None, "bids": dict(remote["bids"]), "decide_at": tick + 1})
                elif entry["status"] == BIDDING and remote["status"] == BIDDING:
                    entry["bids"].update(remote["bids"])
                    entry["decide_at"] = min(entry.get("decide_at", tick + 1), tick + 1)
        self.bus.note_sync_processed(self.agent_id, message.sender_id, tick)

    def _run_auction_timers(self, env, tick):
        """Close auctions whose bid window ended, and restart ones that stalled."""
        for entry in list(self.ledger.values()):
            if entry["status"] == BIDDING and tick >= entry["decide_at"]:
                self._resolve_auction(entry, env, tick)
            elif entry["status"] == NO_BIDS and tick >= entry["retry_at"]:
                self._open_auction(entry["task"], entry["epoch"] + 1, env, tick)
            elif entry["status"] == PROVISIONAL and tick >= entry["confirm_by"]:
                self._open_auction(entry["task"], entry["epoch"] + 1, env, tick)   # winner never confirmed

    def _resolve_auction(self, entry, env, tick):
        """
        Pick the winner. EVERY agent runs this same rule on the bids it heard:
        lowest cost wins, ties go to the lowest agent ID.
        """
        bids = {a: c for a, c in entry["bids"].items() if a not in self.suspected_dead}
        if not bids:
            entry["status"] = NO_BIDS
            entry["retry_at"] = tick + config.RETRY_INTERVAL
            return
        winner_cost, winner_id = min((cost, agent_id) for agent_id, cost in bids.items())
        entry["owner"] = winner_id
        entry["cost"] = winner_cost
        if winner_id == self.agent_id and self.compute_bid(entry["task"], env) is None:
            # I won, but I have won other auctions in the meantime and can no longer
            # afford this one (battery or queue). I stay silent. Everybody, including
            # me, re-auctions after ACCEPT_GRACE. This stops agents over-committing.
            entry["status"] = PROVISIONAL
            entry["confirm_by"] = tick + config.ACCEPT_GRACE
        elif winner_id == self.agent_id:
            entry["status"] = ASSIGNED
            self.enqueue_task(entry["task"])
            self.bus.send(TASK_ACCEPT, self.agent_id, BROADCAST, tick,
                          {"task_id": entry["task"].task_id, "epoch": entry["epoch"], "cost": winner_cost})
            rescue_distance = self.path_length(self.position, entry["task"].pickup, env)
            env.record_assignment(entry["task"].task_id, self.agent_id, tick,
                                  recovery_approach_distance=rescue_distance)   # metrics only
        else:
            entry["status"] = PROVISIONAL
            entry["confirm_by"] = tick + config.ACCEPT_GRACE

    def _on_accept(self, message):
        """
        Someone announced they own a task. Update my ledger.
        Conflict rule: an older epoch is ignored; for the same epoch the lower
        (cost, agent ID) claim wins. If I lose a claim, I drop the task.
        """
        payload = message.payload
        entry = self.ledger.get(payload["task_id"])
        if entry is None or entry["status"] in (DONE, CANCELLED) or payload["epoch"] < entry["epoch"]:
            return
        claim = (payload["cost"], message.sender_id)
        if payload["epoch"] == entry["epoch"] and entry["owner"] is not None:
            if claim > (entry["cost"], entry["owner"]):
                return                                    # the claim I already know is better
        if entry["owner"] == self.agent_id:
            self._drop_task(payload["task_id"])           # I lost a conflict
        entry["epoch"] = payload["epoch"]
        entry["owner"] = message.sender_id
        entry["cost"] = payload["cost"]
        entry["status"] = ASSIGNED

    def _drop_task(self, task_id):
        """Give up a task that has not been picked up yet."""
        self.task_queue = [t for t in self.task_queue if t.task_id != task_id]
        if (self.assigned_task is not None and self.assigned_task.task_id == task_id
                and self.status == GOING_TO_PICKUP):
            self.assigned_task = None
            self.status = IDLE

    # ---------- heartbeats, failure detection and reclaim (Phase 9) ----------
    def _send_heartbeat(self, tick):
        """Tell everybody I am alive, and where I am. Sent every HEARTBEAT_INTERVAL ticks."""
        if (tick + self.agent_id) % config.HEARTBEAT_INTERVAL != 0:        # staggered per agent
            return
        owned = [t.task_id for t in self.task_queue]
        carrying = None
        if self.assigned_task is not None:
            owned.append(self.assigned_task.task_id)
            if self.status == DELIVERING:
                carrying = self.assigned_task.task_id
        self.bus.send(HEARTBEAT, self.agent_id, BROADCAST, tick,
                      {"position": self.position, "battery": round(self.battery), "status": self.status,
                       "owned": owned, "carrying": carrying})

    def _detect_failures(self, env, tick):
        """If a peer has been silent for too long, I decide - on my own - that it is dead."""
        for peer_id, heard_at in list(self.last_heard.items()):
            if peer_id not in self.suspected_dead and tick - heard_at > config.FAILURE_TIMEOUT:
                self._declare_failed(peer_id, env, tick, announce=True)

    def _declare_failed(self, peer_id, env, tick, announce):
        """
        Mark a peer dead and reclaim its tasks from MY OWN ledger copy.
        Every agent does this independently. To avoid a flood of identical messages, only the
        lowest-ID agent that I believe is alive broadcasts the announcement; the others still
        act on their own ledger. Duplicate messages are harmless anyway (same epoch = ignored).
        """
        self.suspected_dead.add(peer_id)
        env.record_detection(peer_id, tick)                       # metrics only
        alive_view = [self.agent_id] + [p for p in self.last_heard if p not in self.suspected_dead]
        i_announce = announce and self.agent_id == min(alive_view)
        if i_announce:
            self.bus.send(AGENT_FAILURE, self.agent_id, BROADCAST, tick,
                          {"failed_id": peer_id, "detect_tick": tick})
        for entry in list(self.ledger.values()):
            if entry["owner"] == peer_id and entry["status"] in (ASSIGNED, PROVISIONAL):
                rescue_task = self._rescue_task(entry["task"], peer_id)
                new_epoch = entry["epoch"] + 1
                if i_announce:
                    self.bus.send(TASK_REASSIGN, self.agent_id, BROADCAST, tick,
                                  {"task": rescue_task, "epoch": new_epoch, "reason": "OWNER_FAILED"})
                self._open_auction(rescue_task, new_epoch, env, tick)

    def _rescue_task(self, task, dead_peer_id):
        """
        The task as it must be re-auctioned. If the dead peer was carrying the parcel,
        the new pickup point is the peer's last heartbeat position (simulation simplification).
        """
        info = self.peer_info.get(dead_peer_id)
        pickup = task.pickup
        if info is not None and info.get("carrying") == task.task_id:
            pickup = info["position"]
        return TaskInfo(task.task_id, pickup, task.destination, task.priority, task.created_tick,
                        task.deadline_tick)

    def _on_reassign(self, payload, env, tick):
        """Someone re-opened a task. Ignore it if I already know that epoch; otherwise join the auction."""
        entry = self.ledger.get(payload["task"].task_id)
        if entry is not None and payload["epoch"] <= entry["epoch"]:
            return                                            # duplicate (I detected the failure myself)
        if entry is not None and entry["owner"] == self.agent_id:
            self._drop_task(payload["task"].task_id)          # others think I failed: let go if I can
        self._open_auction(payload["task"], payload["epoch"], env, tick)

    # ---------- doing the work ----------
    def _start_next_task(self):
        """Take the most urgent (then oldest) task from my queue and start driving."""
        best = min(self.task_queue, key=lambda t: (-t.priority, t.created_tick, t.task_id))
        self.task_queue.remove(best)
        self.assigned_task = best
        self.status = GOING_TO_PICKUP

    def _current_target(self, env):
        """Where should I be heading right now?"""
        if self.status == GOING_TO_CHARGE:
            return self.charger_target
        if self.status == GOING_TO_PICKUP:
            return self.assigned_task.pickup
        if self.status == DELIVERING:
            return self.assigned_task.destination
        if config.WANDER_WHEN_IDLE:
            if self.wander_target is None or self.wander_target == self.position:
                self.wander_target = env.random_free_cell()
            return self.wander_target
        return self.position

    def _handle_arrival(self, env, tick):
        """Switch state when we reach a charger, a pickup point or a destination."""
        if self.status == GOING_TO_CHARGE and self.position == self.charger_target:
            self.status = CHARGING
            self.wander_target = None

        if self.status == GOING_TO_PICKUP and self.position == self.assigned_task.pickup:
            env.record_pickup(self.assigned_task.task_id, tick)
            self.status = DELIVERING

        if self.status == DELIVERING and self.position == self.assigned_task.destination:
            task = self.assigned_task
            env.record_delivery(task.task_id, tick)
            self.tasks_completed += 1
            if self.bus is not None:
                entry = self.ledger.get(task.task_id)
                epoch = entry["epoch"] if entry is not None else 1
                if entry is not None:
                    entry["status"] = DONE
                    entry["completed_tick"] = tick
                self.bus.send(DELIVERY_COMPLETE, self.agent_id, BROADCAST, tick,
                              {"task_id": task.task_id, "epoch": epoch})
            self.assigned_task = None
            self.status = IDLE

    def _charge(self):
        """Gain battery each tick; go back to IDLE when charged enough."""
        previous = self.battery
        self.battery = min(config.BATTERY_MAX, self.battery + config.CHARGE_RATE)
        self.energy_charged += self.battery - previous
        if self.battery >= config.CHARGE_TARGET:
            self.status = IDLE

    def _step_along_path(self, target, env, tick=None):
        """
        Walk one cell towards `target` along an A* route.
        A new route is computed when the target changed, or when the next cell
        on my route has become blocked (the "re-plan" of a dynamic environment).
        """
        if self.path_target != target or not self.path or self.path[0] in self.known_obstacles:
            route = astar(self.position, target, self.known_obstacles, env.width, env.height)
            self.replans += 1
            self.path = route or []
            self.path_target = target
            if self._reroute_pending and route:
                self.successful_reroutes += 1
                self._reroute_pending = False
                if self.bus is not None:
                    self.bus.note_event("REROUTE_SUCCESS", {"agent_id": self.agent_id, "target": target},
                                        0 if tick is None else tick,
                                        once_key=("reroute", self.agent_id, self.route_reroutes))
            if not self.path:
                return                                    # no route right now: wait
        self._move_to(self.path.pop(0))

    def _move_to(self, new_cell):
        """Actually move, paying battery for the step."""
        self.position = new_cell
        self.battery -= config.ENERGY_PER_CELL
        self.energy_used += config.ENERGY_PER_CELL
        self.distance_travelled += 1
