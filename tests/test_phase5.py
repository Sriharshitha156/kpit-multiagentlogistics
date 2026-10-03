"""Basic checks for Phase 5. Run from the project folder:  python -m unittest discover -s tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from environment import Environment
from simulation import Simulation


class TestPhase5(unittest.TestCase):
    def test_same_seed_gives_same_map(self):
        a, b = Environment(1), Environment(1)
        self.assertEqual(a.obstacles, b.obstacles)
        self.assertEqual(a.chargers, b.chargers)

    def test_chargers_are_never_blocked(self):
        env = Environment(5)
        for charger in env.chargers:
            self.assertNotIn(charger, env.obstacles)

    def test_agents_never_stand_on_obstacles(self):
        sim = Simulation(seed=3)
        for _ in range(500):
            sim.step()
            for agent in sim.agents:
                self.assertTrue(sim.env.is_free(agent.position))

    def test_battery_never_negative(self):
        sim = Simulation(seed=4)
        for _ in range(800):
            sim.step()
            for agent in sim.agents:
                self.assertGreaterEqual(agent.battery, 0)

    def test_failed_agent_stays_put(self):
        sim = Simulation(seed=2)
        sim.fail_agent(1)
        position = sim.agents[0].position
        for _ in range(30):
            sim.step()
        self.assertEqual(sim.agents[0].position, position)

    def test_same_seed_same_run(self):
        a, b = Simulation(seed=7), Simulation(seed=7)
        for _ in range(200):
            a.step()
            b.step()
        self.assertEqual([x.position for x in a.agents], [x.position for x in b.agents])


if __name__ == "__main__":
    unittest.main()
