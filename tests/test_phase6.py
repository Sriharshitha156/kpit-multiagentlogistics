"""Checks for Phase 6 (baseline B1). Run from the project folder:  python -m unittest discover -s tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from metrics import summarize
from simulation import Simulation
from task import COMPLETED, OPEN, Task


def quiet_simulation(seed, num_agents):
    """A baseline-B1 simulation where tasks only appear when WE create them."""
    config.TASK_SPAWN_PROBABILITY = 0.0
    return Simulation(seed=seed, num_agents=num_agents, strategy="B1")


class TestBaselineB1(unittest.TestCase):
    def tearDown(self):
        config.TASK_SPAWN_PROBABILITY = 0.08       # restore the default

    def test_nearest_idle_agent_gets_the_task(self):
        sim = quiet_simulation(1, 2)
        sim.agents[0].position = (0, 0)
        sim.agents[1].position = (29, 19)
        sim.env.add_task(Task(1, (1, 1), (5, 5), 2, 0))
        sim.dispatcher.step(sim.env, sim.agents, 0)
        self.assertEqual(sim.env.tasks[0].owner_id, 1)

    def test_a_task_gets_delivered(self):
        sim = quiet_simulation(1, 3)
        task = sim.env.spawn_task(0)
        for _ in range(400):
            sim.step()
        self.assertEqual(task.status, COMPLETED)
        self.assertEqual(summarize(sim)["completed"], 1)

    def test_failed_owner_means_lost_task(self):
        sim = quiet_simulation(1, 3)
        task = sim.env.spawn_task(0)
        sim.step()                                  # dispatcher assigns it
        self.assertIsNotNone(task.owner_id)
        sim.fail_agent(task.owner_id)
        for _ in range(100):
            sim.step()
        self.assertNotEqual(task.status, COMPLETED)  # B1 has no recovery
        self.assertEqual(summarize(sim)["lost"], 1)

    def test_offline_dispatcher_assigns_nothing(self):
        sim = quiet_simulation(1, 3)
        sim.dispatcher.online = False
        for _ in range(3):
            sim.env.spawn_task(0)
        for _ in range(30):
            sim.step()
        self.assertTrue(all(t.status == OPEN for t in sim.env.tasks))


if __name__ == "__main__":
    unittest.main()
