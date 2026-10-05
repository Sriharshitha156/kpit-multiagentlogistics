"""Communication partition and deterministic task-ledger synchronization tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from communication import BROADCAST, MessageBus
from simulation import Simulation


class TestCommunicationPartition(unittest.TestCase):
    def setUp(self):
        self.old_spawn_probability = config.TASK_SPAWN_PROBABILITY
        self.old_loss_probability = config.LOSS_PROBABILITY
        config.TASK_SPAWN_PROBABILITY = 0.0
        config.LOSS_PROBABILITY = 0.0

    def tearDown(self):
        config.TASK_SPAWN_PROBABILITY = self.old_spawn_probability
        config.LOSS_PROBABILITY = self.old_loss_probability

    def test_partition_keeps_messages_inside_groups_and_drops_cross_group_messages(self):
        bus = MessageBus(seed=1)
        bus.set_alive([1, 2, 3, 4])
        bus.set_partition(([1, 2], [3, 4]))
        bus.send("LOCAL_TEST", 1, BROADCAST, 0, {})
        bus.deliver(config.MESSAGE_DELAY)
        self.assertEqual(len(bus.collect(2)), 1)
        self.assertEqual(bus.collect(3), [])
        self.assertEqual(bus.collect(4), [])
        self.assertEqual(bus.messages_partitioned, 2)

    def test_each_group_can_award_a_task_locally_then_sync_resolves_conflict(self):
        sim = Simulation(seed=21, num_agents=4, strategy="AUCTION")
        task = sim.new_task()
        sim.agents[0].position = task.pickup
        sim.agents[2].position = task.pickup
        for agent in (sim.agents[1], sim.agents[3]):
            agent.status = "CHARGING"  # not eligible, but remains alive during the short demo

        sim.partition_network(([1, 2], [3, 4]))
        for _ in range(4):
            sim.step()

        first_group = {sim.agents[i].ledger[task.task_id]["owner"] for i in (0, 1)}
        second_group = {sim.agents[i].ledger[task.task_id]["owner"] for i in (2, 3)}
        self.assertEqual(first_group, {1})
        self.assertEqual(second_group, {3})
        self.assertGreater(sim.bus.messages_partitioned, 0)

        self.assertTrue(sim.restore_network())
        for _ in range(4):
            sim.step()

        owners = {agent.ledger[task.task_id]["owner"] for agent in sim.agents}
        self.assertEqual(owners, {1})  # equal bids resolve to the lower agent ID
        self.assertTrue(sim.bus.sync_complete)
        conflict_events = [event for event in sim.bus.log if event[1] == "SYNC_CONFLICT"]
        self.assertTrue(conflict_events)

    def test_restore_without_a_partition_is_a_noop(self):
        sim = Simulation(seed=22, num_agents=2, strategy="AUCTION")
        self.assertFalse(sim.restore_network())
        self.assertFalse(sim.bus.partitioned)


if __name__ == "__main__":
    unittest.main()
