"""Checks for Phase 11 (demo presets, message feed, split-screen fairness). Run:  python -m unittest discover -s tests"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import scenarios
from communication import describe_message, HEARTBEAT, TASK_BID
from simulation import Simulation


class TestPresets(unittest.TestCase):
    def setUp(self):
        config.TASK_SPAWN_PROBABILITY = 0.0

    def tearDown(self):
        config.TASK_SPAWN_PROBABILITY = 0.08

    def pair(self):
        return [Simulation(seed=9, strategy="B2"), Simulation(seed=9, strategy="AUCTION")]

    def test_both_simulations_start_identical(self):
        b2, auction = self.pair()
        self.assertEqual(b2.env.obstacles, auction.env.obstacles)
        self.assertEqual(b2.env.chargers, auction.env.chargers)
        self.assertEqual([a.position for a in b2.agents], [a.position for a in auction.agents])

    def test_rush_hour_creates_the_same_orders_in_both(self):
        sims = self.pair()
        scenarios.rush_hour(sims, count=5)
        self.assertEqual(len(sims[0].env.tasks), 5)
        self.assertEqual([(t.pickup, t.destination) for t in sims[0].env.tasks],
                         [(t.pickup, t.destination) for t in sims[1].env.tasks])

    def test_failure_storm_fails_the_same_vehicles_and_keeps_one_alive(self):
        sims = self.pair()
        scenarios.failure_storm(sims, count=99, rng=random.Random(1))
        failed = [{a.agent_id for a in s.agents if not a.is_alive()} for s in sims]
        self.assertEqual(failed[0], failed[1])
        self.assertEqual(sims[0].alive_count(), 1)

    def test_blocked_road_blocks_the_same_cells_and_keeps_the_map_connected(self):
        sims = self.pair()
        before = set(sims[0].env.obstacles)
        scenarios.blocked_road(sims, count=10)
        self.assertGreater(len(sims[0].env.obstacles), len(before))
        self.assertEqual(sims[0].env.obstacles, sims[1].env.obstacles)
        self.assertTrue(sims[0].env._is_connected(sims[0].env.obstacles))


class TestMessageFeed(unittest.TestCase):
    def tearDown(self):
        config.TASK_SPAWN_PROBABILITY = 0.08

    def test_bus_keeps_a_log_of_transmissions(self):
        config.TASK_SPAWN_PROBABILITY = 0.0
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        sim.new_task()
        for _ in range(8):
            sim.step()
        types = [entry[1] for entry in sim.bus.log]
        self.assertIn("TASK_REQUEST", types)
        self.assertIn(TASK_BID, types)
        self.assertIn(HEARTBEAT, types)

    def test_describe_message_is_readable(self):
        text = describe_message(TASK_BID, 3, {"task_id": 7, "epoch": 1, "cost": 14.25})
        self.assertEqual(text, "A3 -> ALL  TASK_BID  #7 cost 14.2")


if __name__ == "__main__":
    unittest.main()
