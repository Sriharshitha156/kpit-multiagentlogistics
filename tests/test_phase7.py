"""Checks for Phase 7 (auctions, bidding, message bus). Run:  python -m unittest discover -s tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from communication import BROADCAST, MessageBus, TASK_BID
from metrics import summarize
from simulation import Simulation
from task import COMPLETED, TaskInfo


class TestAuction(unittest.TestCase):
    def setUp(self):
        config.TASK_SPAWN_PROBABILITY = 0.0       # tasks only appear when the test creates them

    def tearDown(self):
        config.TASK_SPAWN_PROBABILITY = 0.08
        config.LOSS_PROBABILITY = 0.0

    def test_bus_counts_broadcasts(self):
        bus = MessageBus()
        bus.set_alive([1, 2, 3])
        bus.send(TASK_BID, 1, BROADCAST, 0, {})
        bus.deliver(5)
        self.assertEqual(bus.messages_sent, 1)           # one transmission
        self.assertEqual(bus.messages_delivered, 2)      # two receivers (not the sender)

    def test_every_agent_agrees_on_the_winner(self):
        sim = Simulation(seed=1, num_agents=5, strategy="AUCTION")
        task = sim.new_task()
        costs = {a.agent_id: a.compute_bid(task.describe(), sim.env) for a in sim.agents}
        expected = min((c, i) for i, c in costs.items() if c is not None)[1]
        for _ in range(10):
            sim.step()
        owners = {a.ledger[task.task_id]["owner"] for a in sim.agents}
        self.assertEqual(owners, {expected})             # all five ledgers name the same winner
        self.assertEqual(task.owner_id, expected)

    def test_message_bus_keeps_a_bid_and_winner_audit_record(self):
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        task = sim.new_task()
        for _ in range(10):
            sim.step()

        record = sim.bus.auction_history[0]
        self.assertEqual(record["task_id"], task.task_id)
        self.assertEqual(record["priority"], task.priority)
        self.assertTrue(record["bids"])
        self.assertIn(task.owner_id, record["accepts"])

    def test_tie_goes_to_lowest_id(self):
        sim = Simulation(seed=1, num_agents=3, strategy="AUCTION")
        task = sim.new_task()
        for agent in sim.agents:
            agent.position = task.pickup                 # identical situation -> identical cost
        for _ in range(10):
            sim.step()
        self.assertEqual(task.owner_id, 1)

    def test_bid_route_uses_the_same_priority_order_as_execution(self):
        sim = Simulation(seed=1, num_agents=1, strategy="AUCTION")
        agent = sim.agents[0]
        agent.position = (0, 0)
        agent.known_obstacles.clear()
        agent._length_cache.clear()
        agent.task_queue = [TaskInfo(1, (1, 0), (2, 0), 1, 0)]
        urgent = TaskInfo(2, (10, 0), (11, 0), 3, 1)

        total_distance, final_position, distance_to_urgent_pickup = agent._planned_work(urgent, sim.env)

        self.assertEqual(distance_to_urgent_pickup, 10)  # urgent job runs before the queued low-priority job
        self.assertEqual(total_distance, 22)
        self.assertEqual(final_position, (2, 0))

    def test_low_battery_agent_does_not_win(self):
        sim = Simulation(seed=1, num_agents=2, strategy="AUCTION")
        task = sim.new_task()
        for agent in sim.agents:
            agent.position = task.pickup
        sim.agents[0].battery = 1.0                      # cannot finish any delivery
        self.assertIsNone(sim.agents[0].compute_bid(task.describe(), sim.env))
        for _ in range(10):
            sim.step()
        self.assertEqual(task.owner_id, 2)

    def test_a_task_gets_delivered_by_auction(self):
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        task = sim.new_task()
        for _ in range(500):
            sim.step()
        self.assertEqual(task.status, COMPLETED)

    def test_still_works_with_message_loss(self):
        config.TASK_SPAWN_PROBABILITY = 0.08
        config.LOSS_PROBABILITY = 0.2
        sim = Simulation(seed=2, num_agents=6, strategy="AUCTION")
        for _ in range(600):
            sim.step()
        self.assertGreater(summarize(sim)["completed"], 0)

    def test_central_b2_picks_lowest_cost(self):
        sim = Simulation(seed=1, num_agents=3, strategy="B2")
        task = sim.new_task()
        sim.agents[0].position = (0, 0)
        sim.agents[1].position = (29, 19)
        sim.agents[2].position = task.pickup
        sim.step()
        self.assertEqual(task.owner_id, 3)


if __name__ == "__main__":
    unittest.main()
