"""Checks for Phase 10 (experiment runner). Run:  python -m unittest discover -s tests"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))

import config
import run_experiments as runner


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
