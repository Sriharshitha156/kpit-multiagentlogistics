"""Checks for Phase 10 (experiment runner). Run:  python -m unittest discover -s tests"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))

import config
import run_experiments as runner
from simulation import Simulation


class TestRunner(unittest.TestCase):
    def job(self, strategy="AUCTION", failures=0, **overrides):
        return {"experiment": "t", "group": "", "x": 0, "strategy": strategy, "seed": 5, "num_agents": 6,
                "overrides": overrides, "failures": failures, "outage": False}

    def test_same_job_gives_identical_results(self):
        a = runner.run_job(self.job(), 200)
        b = runner.run_job(self.job(), 200)
        self.assertEqual(a, b)

    def test_overrides_are_restored_after_a_run(self):
        before = config.FAILURE_TIMEOUT
        runner.run_job(self.job(FAILURE_TIMEOUT=25), 50)
        self.assertEqual(config.FAILURE_TIMEOUT, before)

    def test_every_strategy_sees_the_same_failures(self):
        self.assertEqual(runner.failing_agents(7, 10, 3), runner.failing_agents(7, 10, 3))
        self.assertEqual(len(set(runner.failing_agents(7, 10, 3))), 3)

    def test_task_schedule_is_repeatable_and_shared_across_strategies(self):
        schedule = runner.build_task_schedule(23, 80, 0.2)
        self.assertEqual(schedule, runner.build_task_schedule(23, 80, 0.2))
        task_sets = []
        for strategy in ("B1", "B2", "AUCTION"):
            sim = Simulation(seed=23, num_agents=6, strategy=strategy, task_schedule=schedule)
            for _ in range(80):
                sim.step()
            task_sets.append([(t.created_tick, t.pickup, t.destination, t.priority) for t in sim.env.tasks])
        self.assertEqual(task_sets[0], task_sets[1])
        self.assertEqual(task_sets[1], task_sets[2])

    def test_fixed_count_schedule_creates_requested_number_of_orders(self):
        schedule = runner.build_task_schedule(31, 40, 0.0, task_count=12)
        self.assertEqual(len(schedule), 12)
        sim = Simulation(seed=31, num_agents=5, strategy="B1", task_schedule=schedule)
        for _ in range(40):
            sim.step()
        self.assertEqual(len(sim.env.tasks), 12)

    def test_scale_run_records_measured_compute_time(self):
        job = self.job()
        job.update({"paired_tasks": True, "track_runtime": True, "task_count": 3})
        row = runner.run_job(job, 30)
        self.assertGreater(row["compute_seconds"], 0)

    def test_aggregate_computes_mean_and_std(self):
        rows = [{"experiment": "e", "group": "", "x": "1", "strategy": "B2", "seed": s,
                 **{m: "" for m in runner.METRICS}} for s in (1, 2, 3)]
        for row, value in zip(rows, ("2", "4", "6")):
            row["completed"] = value
        summary = runner.aggregate(rows)[0]
        self.assertEqual(summary["completed_mean"], 4)
        self.assertEqual(summary["completed_std"], 2)
        self.assertEqual(summary["n"], 3)


if __name__ == "__main__":
    unittest.main()
