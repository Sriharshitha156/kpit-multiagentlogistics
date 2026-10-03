"""Checks for Phase 9 (heartbeats, failure detection, reclaim). Run:  python -m unittest discover -s tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from environment import manhattan
from metrics import summarize
from simulation import Simulation
from task import COMPLETED


def run_until_owned_and_working(sim, task, limit=60):
    """Step until the task has an owner that has started driving."""
    for _ in range(limit):
        sim.step()
        if task.owner_id is not None and sim.agents[task.owner_id - 1].assigned_task is not None:
            return sim.agents[task.owner_id - 1]
    raise AssertionError("task never got a working owner")


class TestFailureRecovery(unittest.TestCase):
    def setUp(self):
        config.TASK_SPAWN_PROBABILITY = 0.0

    def tearDown(self):
        config.TASK_SPAWN_PROBABILITY = 0.08
        config.LOSS_PROBABILITY = 0.0

    def test_heartbeats_are_sent(self):
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        for _ in range(12):
            sim.step()
        self.assertGreater(sim.bus.sent_by_type.get("HEARTBEAT", 0), 0)

    def test_every_peer_detects_the_failure_and_nobody_else(self):
        sim = Simulation(seed=1, num_agents=5, strategy="AUCTION")
        for _ in range(5):
            sim.step()
        sim.fail_agent(2)
        for _ in range(config.FAILURE_TIMEOUT + 8):
            sim.step()
        for agent in sim.agents:
            if agent.is_alive():
                self.assertEqual(agent.suspected_dead, {2})

    def test_orphaned_task_is_reclaimed_and_delivered(self):
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        task = sim.new_task()
        owner = run_until_owned_and_working(sim, task)
        sim.fail_agent(owner.agent_id)
        for _ in range(400):
            sim.step()
        self.assertEqual(task.status, COMPLETED)
        self.assertEqual(task.reassign_count, 1)
        self.assertNotEqual(task.owner_id, owner.agent_id)
        m = summarize(sim)
        self.assertEqual(m["reassigned_tasks"], 1)
        self.assertIsNotNone(m["avg_reassignment_time"])
        self.assertLess(m["avg_reassignment_time"], 40)

    def test_ledgers_agree_after_reclaim(self):
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        task = sim.new_task()
        owner = run_until_owned_and_working(sim, task)
        sim.fail_agent(owner.agent_id)
        for _ in range(400):
            sim.step()
        epochs = {a.ledger[task.task_id]["epoch"] for a in sim.agents if a.is_alive()}
        self.assertEqual(epochs, {2})                    # every survivor saw exactly one re-auction

    def test_rescue_point_is_near_where_the_carrier_died(self):
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        task = sim.new_task()
        owner = run_until_owned_and_working(sim, task)
        for _ in range(300):
            if owner.status == "DELIVERING":
                break
            sim.step()
        for _ in range(config.HEARTBEAT_INTERVAL + 1):    # let a heartbeat report "carrying"
            sim.step()
        if owner.status != "DELIVERING":
            self.skipTest("delivery finished too quickly for this check")
        died_at = owner.position
        sim.fail_agent(owner.agent_id)
        for _ in range(config.FAILURE_TIMEOUT + 8):
            sim.step()
        survivor = next(a for a in sim.agents if a.is_alive())
        rescue_pickup = survivor.ledger[task.task_id]["task"].pickup
        self.assertLessEqual(manhattan(rescue_pickup, died_at), config.HEARTBEAT_INTERVAL + 1)

    def test_b2_recovers_almost_instantly(self):
        sim = Simulation(seed=1, num_agents=4, strategy="B2")
        task = sim.new_task()
        owner = run_until_owned_and_working(sim, task)
        sim.fail_agent(owner.agent_id)
        for _ in range(400):
            sim.step()
        self.assertEqual(task.status, COMPLETED)
        self.assertEqual(task.reassign_count, 1)
        self.assertLessEqual(summarize(sim)["avg_reassignment_time"], 3)

    def test_b1_never_recovers(self):
        sim = Simulation(seed=1, num_agents=4, strategy="B1")
        task = sim.new_task()
        owner = run_until_owned_and_working(sim, task)
        sim.fail_agent(owner.agent_id)
        for _ in range(400):
            sim.step()
        self.assertNotEqual(task.status, COMPLETED)

    def test_no_false_alarms_on_a_healthy_network(self):
        config.TASK_SPAWN_PROBABILITY = 0.08
        sim = Simulation(seed=3, num_agents=8, strategy="AUCTION")
        for _ in range(600):
            sim.step()
        self.assertEqual(summarize(sim)["false_suspicions"], 0)


if __name__ == "__main__":
    unittest.main()
