"""Regression checks for the remaining project edge cases."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from communication import Message, TASK_BID
from metrics import summarize
from simulation import Simulation
from task import CANCELLED, TaskInfo


class TestProjectEdgeCases(unittest.TestCase):
    def setUp(self):
        self.old_spawn_probability = config.TASK_SPAWN_PROBABILITY
        self.old_loss_probability = config.LOSS_PROBABILITY
        config.TASK_SPAWN_PROBABILITY = 0.0
        config.LOSS_PROBABILITY = 0.0

    def tearDown(self):
        config.TASK_SPAWN_PROBABILITY = self.old_spawn_probability
        config.LOSS_PROBABILITY = self.old_loss_probability

    def test_no_available_agents_leaves_task_open(self):
        sim = Simulation(seed=4, num_agents=3, strategy="AUCTION")
        for agent in sim.agents:
            sim.fail_agent(agent.agent_id)
        task = sim.new_task()
        for _ in range(5):
            sim.step()
        self.assertIsNone(task.owner_id)
        self.assertEqual(task.status, "OPEN")

    def test_all_low_battery_agents_decline_to_bid(self):
        sim = Simulation(seed=5, num_agents=3, strategy="AUCTION")
        for agent in sim.agents:
            agent.battery = 1.0
        task = sim.new_task()
        for _ in range(5):
            sim.step()
        self.assertIsNone(task.owner_id)
        accepts = [entry for entry in sim.bus.log if entry[1] == "TASK_ACCEPT"]
        self.assertEqual(accepts, [])

    def test_unreachable_route_is_not_bid_on(self):
        sim = Simulation(seed=6, num_agents=1, strategy="AUCTION")
        agent = sim.agents[0]
        agent.position = (1, 1)
        agent.known_obstacles.update((2, y) for y in range(sim.env.height))
        agent._length_cache.clear()
        task = TaskInfo(999, (1, 1), (3, 1), 2, sim.tick)
        self.assertIsNone(agent.compute_bid(task, sim.env))

    def test_duplicate_bid_from_same_agent_is_idempotent(self):
        sim = Simulation(seed=7, num_agents=2, strategy="AUCTION")
        task = sim.new_task()
        for _ in range(config.MESSAGE_DELAY + 1):
            sim.step()
        ledger = sim.agents[0].ledger[task.task_id]
        bidder = sim.agents[1].agent_id
        payload = {"task_id": task.task_id, "epoch": ledger["epoch"], "cost": 12.5}
        duplicate = Message(900, TASK_BID, bidder, sim.agents[0].agent_id, sim.tick, sim.tick, payload)
        sim.agents[0]._on_bid(duplicate)
        sim.agents[0]._on_bid(duplicate)
        self.assertEqual(ledger["bids"][bidder], 12.5)
        self.assertEqual(list(ledger["bids"]).count(bidder), 1)

    def test_simultaneous_failures_are_detected_by_survivors(self):
        sim = Simulation(seed=8, num_agents=5, strategy="AUCTION")
        for _ in range(6):
            sim.step()
        sim.fail_agent(2)
        sim.fail_agent(4)
        for _ in range(config.FAILURE_TIMEOUT + 10):
            sim.step()
        for agent in sim.agents:
            if agent.is_alive():
                self.assertEqual(agent.suspected_dead, {2, 4})

    def test_simulation_continues_after_every_agent_fails(self):
        sim = Simulation(seed=9, num_agents=3, strategy="AUCTION")
        for agent in sim.agents:
            sim.fail_agent(agent.agent_id)
        for _ in range(3):
            sim.step()
        self.assertEqual(sim.alive_count(), 0)
        self.assertEqual(sim.failed_count(), 3)

    def test_cancelling_open_auction_removes_order_from_every_vehicle(self):
        sim = Simulation(seed=10, num_agents=3, strategy="AUCTION")
        task = sim.new_task()
        self.assertTrue(sim.cancel_task(task.task_id))
        self.assertFalse(sim.cancel_task(task.task_id))
        for _ in range(4):
            sim.step()
        self.assertEqual(task.status, CANCELLED)
        self.assertIsNone(task.owner_id)
        self.assertTrue(all(a.ledger[task.task_id]["status"] == "CANCELLED" for a in sim.agents))
        self.assertEqual(summarize(sim)["cancelled"], 1)

    def test_central_dispatchers_ignore_cancelled_orders(self):
        for strategy in ("B1", "B2"):
            sim = Simulation(seed=11, num_agents=2, strategy=strategy)
            task = sim.new_task()
            self.assertTrue(sim.cancel_task(task.task_id))
            sim.step()
            self.assertIsNone(task.owner_id)
            self.assertEqual(task.status, CANCELLED)

    def test_assigned_task_cannot_be_cancelled(self):
        sim = Simulation(seed=12, num_agents=2, strategy="B1")
        task = sim.new_task()
        sim.step()
        self.assertIsNotNone(task.owner_id)
        self.assertFalse(sim.cancel_task(task.task_id))
        self.assertNotEqual(task.status, CANCELLED)


if __name__ == "__main__":
    unittest.main()
