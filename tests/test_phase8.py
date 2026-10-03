"""Checks for Phase 8 (A*, obstacles). Run:  python -m unittest discover -s tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from environment import Environment, manhattan
from metrics import summarize
from pathfinding import astar
from simulation import Simulation


class TestAStar(unittest.TestCase):
    def test_empty_grid_path_is_manhattan_length(self):
        path = astar((0, 0), (7, 4), set(), 10, 10)
        self.assertEqual(len(path), manhattan((0, 0), (7, 4)))
        self.assertEqual(path[-1], (7, 4))

    def test_path_goes_around_a_wall(self):
        wall = {(5, y) for y in range(9)}                # gap only at (5, 9)
        path = astar((0, 0), (9, 0), wall, 10, 10)
        self.assertEqual(len(path), 27)                  # 14 down-and-across to the gap + 13 back up
        self.assertTrue(all(cell not in wall for cell in path))

    def test_no_route_returns_none(self):
        enclosed = {(4, 5), (6, 5), (5, 4), (5, 6)}
        self.assertIsNone(astar((0, 0), (5, 5), enclosed, 10, 10))

    def test_start_equals_goal(self):
        self.assertEqual(astar((3, 3), (3, 3), set(), 10, 10), [])


class TestDynamicWorld(unittest.TestCase):
    def tearDown(self):
        config.OBSTACLE_DENSITY = 0.10
        config.TASK_SPAWN_PROBABILITY = 0.08

    def test_generated_maps_are_connected(self):
        config.OBSTACLE_DENSITY = 0.20
        for seed in range(1, 6):
            env = Environment(seed)
            self.assertTrue(env._is_connected(env.obstacles))

    def test_protected_cells_cannot_be_blocked(self):
        sim = Simulation(seed=1, num_agents=3, strategy="AUCTION")
        self.assertFalse(sim.env.add_obstacle(sim.env.chargers[0]))
        self.assertIsNone(sim.add_obstacle(sim.agents[0].position))

    def test_agents_replan_and_never_enter_new_obstacles(self):
        sim = Simulation(seed=1, num_agents=4, strategy="AUCTION")
        for _ in range(30):
            sim.step()
        for _ in range(15):
            sim.add_obstacle()
        for _ in range(400):
            sim.step()
            for agent in sim.agents:
                self.assertNotIn(agent.position, sim.env.obstacles)
        self.assertGreater(summarize(sim)["completed"], 0)

    def test_blocked_cell_changes_the_bid_distance(self):
        sim = Simulation(seed=1, num_agents=1, strategy="AUCTION")
        agent = sim.agents[0]
        wall = {(5, y) for y in range(sim.env.height - 1)}
        agent.known_obstacles = wall
        direct = manhattan((0, 0), (9, 0))
        self.assertGreater(agent.path_length((0, 0), (9, 0), sim.env), direct)


if __name__ == "__main__":
    unittest.main()
