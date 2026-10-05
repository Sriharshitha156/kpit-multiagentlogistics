"""
baseline_dispatcher.py - the two CENTRAL baselines our decentralized fleet is compared with.

B1 and B2 both use A* distances (through the agents' own map).

Both are controlled by ONE central object (a single point of failure) that reads
every agent's true state (perfect information).

B1 "naive":   gives each task to the NEAREST IDLE agent. No battery check.
B2 "smart":   gives each task to the LOWEST-COST FEASIBLE agent, using exactly the
              same cost function and battery rule as our auction agents.
              Comparing B2 with the auction isolates the effect of decentralization.

B1 never recovers tasks from failed agents (they are simply lost).
B2 recovers them INSTANTLY, because it has perfect, immediate knowledge of every failure.
That makes B2 the best a central design can do, so it is the fair baseline to compare against.
"""

from task import OPEN


def _waiting_tasks(env):
    """Open tasks, most urgent first, then oldest first."""
    waiting = [t for t in env.tasks if t.status == OPEN]
    waiting.sort(key=lambda t: (-t.priority, t.created_tick, t.task_id))
    return waiting


class CentralDispatcherB1:
    """Assigns waiting tasks to the nearest idle agent, once per tick."""

    def __init__(self):
        self.online = True          # set to False to simulate a dispatcher outage

    def step(self, env, agents, tick):
        if not self.online:
            return
        for task in _waiting_tasks(env):
            idle_agents = [a for a in agents if a.is_available()]
            if not idle_agents:
                break
            def distance(a):
                d = a.path_length(a.position, task.pickup, env)
                return 10 ** 9 if d is None else d
            best = min(idle_agents, key=lambda a: (distance(a), a.agent_id))
            best.enqueue_task(task.describe())
            rescue_distance = best.path_length(best.position, task.pickup, env)
            env.record_assignment(task.task_id, best.agent_id, tick,
                                  recovery_approach_distance=rescue_distance)


class CentralDispatcherB2:
    """Assigns each waiting task to the agent with the lowest feasible bid cost."""

    def __init__(self):
        self.online = True

    def _recover_orphans(self, env, agents):
        """Put every task whose owner has failed back on the waiting list (perfect knowledge)."""
        failed = {a.agent_id: a for a in agents if not a.is_alive()}
        for task in env.tasks:
            if task.status in ("ASSIGNED", "PICKED_UP") and task.owner_id in failed:
                if task.status == "PICKED_UP":
                    task.pickup = failed[task.owner_id].position     # the parcel is where the vehicle died
                task.status = OPEN        # owner_id is kept so the metrics can time the recovery

    def step(self, env, agents, tick):
        if not self.online:
            return
        self._recover_orphans(env, agents)
        for task in _waiting_tasks(env):
            info = task.describe()
            bids = []
            for agent in agents:
                if agent.is_alive():
                    cost = agent.compute_bid(info, env)
                    if cost is not None:
                        bids.append((cost, agent.agent_id, agent))
            if bids:
                cost, agent_id, best = min(bids, key=lambda b: (b[0], b[1]))
                best.enqueue_task(info)
                rescue_distance = best.path_length(best.position, info.pickup, env)
                env.record_assignment(task.task_id, agent_id, tick,
                                      recovery_approach_distance=rescue_distance)
