"""
simulation.py - the tick loop. It only advances time.

Depending on config.STRATEGY it runs:
  "B1"      central dispatcher, nearest idle agent
  "B2"      central dispatcher, same cost + battery rule as the agents
  "AUCTION" no dispatcher at all: agents decide through messages
"""

import config
from agent import Agent
from baseline_dispatcher import CentralDispatcherB1, CentralDispatcherB2
from communication import BROADCAST, DESK, MessageBus, TASK_REQUEST
from environment import Environment


class Simulation:
    """Holds the environment, agents and (for baselines) the dispatcher."""

    def __init__(self, seed=config.RANDOM_SEED, num_agents=config.NUM_AGENTS, strategy=None):
        self.strategy = strategy or config.STRATEGY
        self.env = Environment(seed)
        self.tick = 0
        # Only the decentralized strategy needs a network.
        self.bus = MessageBus(seed + 1000) if self.strategy == "AUCTION" else None
        self.agents = []
        for i in range(num_agents):
            start = self.env.random_free_cell()
            self.agents.append(Agent(agent_id=i + 1, start_position=start, bus=self.bus,
                                     known_obstacles=self.env.obstacles,
                                     peer_ids=[j + 1 for j in range(num_agents) if j != i]))
        self.dispatcher = None
        if self.strategy == "B1":
            self.dispatcher = CentralDispatcherB1()
        elif self.strategy == "B2":
            self.dispatcher = CentralDispatcherB2()
        self._refresh_alive()

    def _refresh_alive(self):
        if self.bus is not None:
            self.bus.set_alive([a.agent_id for a in self.agents if a.is_alive()])

    def new_task(self, pickup=None, destination=None, priority=None):
        """
        An order arrives. The order desk only ANNOUNCES it to everyone (auction mode).
        It never decides who takes it.
        """
        task = self.env.spawn_task(self.tick, pickup=pickup, destination=destination, priority=priority)
        if self.bus is not None:
            self.bus.send(TASK_REQUEST, DESK, BROADCAST, self.tick, {"task": task.describe(), "epoch": 1})
        return task

    def add_obstacle(self, cell=None):
        """
        Block a new cell (a changing road condition) and tell every living agent.
        Cells that are chargers, agent positions, or the ends of unfinished tasks are
        protected, and so is any cell whose blocking would split the map.
        Returns the blocked cell, or None if nothing could be blocked.
        """
        protected = {a.position for a in self.agents}
        for task in self.env.tasks:
            if task.status != "COMPLETED":
                protected.add(task.pickup)
                protected.add(task.destination)
        if cell is None:
            for _ in range(50):
                candidate = self.env.random_free_cell()
                if self.env.add_obstacle(candidate, protected):
                    cell = candidate
                    break
            else:
                return None
        elif not self.env.add_obstacle(cell, protected):
            return None
        for agent in self.agents:                  # a sensor event, not agent-to-agent traffic
            agent.perceive_obstacle(cell)
        return cell

    def step(self):
        """Advance the world by exactly one tick."""
        self.tick += 1
        self._refresh_alive()

        # 1. New delivery request?
        if (self.env.rng.random() < config.TASK_SPAWN_PROBABILITY
                and self.env.open_task_count() < config.MAX_OPEN_TASKS):
            self.new_task()

        # 1b. Road conditions may change.
        if config.OBSTACLE_EVENT_PROBABILITY > 0 and self.env.rng.random() < config.OBSTACLE_EVENT_PROBABILITY:
            self.add_obstacle()

        # 2. The network delivers messages that have arrived.
        if self.bus is not None:
            self.bus.deliver(self.tick)

        # 3. Central baselines only: the dispatcher assigns tasks.
        if self.dispatcher is not None:
            self.dispatcher.step(self.env, self.agents, self.tick)

        # 4. Every agent thinks and moves. Shuffled order = no agent is favoured.
        order = list(self.agents)
        self.env.rng.shuffle(order)
        for agent in order:
            agent.update(self.env, self.tick)
        self._note_failures()

    def _note_failures(self):
        """Record the true failure time of each agent (ground truth for the metrics only)."""
        for agent in self.agents:
            if agent.status == "FAILED" and agent.agent_id not in self.env.failure_ticks:
                failure_tick = agent.failed_tick if agent.failed_tick is not None else self.tick
                self.env.failure_ticks[agent.agent_id] = failure_tick
                self.env.record_agent_failure(agent.agent_id, failure_tick)

    def fail_agent(self, agent_id, reason="CLICKED"):
        """Kill an agent (used by the click-to-fail demo)."""
        for agent in self.agents:
            if agent.agent_id == agent_id and agent.is_alive():
                agent.fail(reason, self.tick)
        self._note_failures()

    def alive_count(self):
        return sum(1 for a in self.agents if a.is_alive())

    def failed_count(self):
        return len(self.agents) - self.alive_count()
