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
from metrics import summarize


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

    def test_emergency_priority_changes_only_priority_not_scheduled_locations(self):
        regular = runner.build_task_schedule(44, 80, 0.0, task_count=20, task_priority=1)
        emergency = runner.build_task_schedule(44, 80, 0.0, task_count=20, task_priority=3)
        self.assertEqual([(t, p, d) for t, p, d, _ in regular],
                         [(t, p, d) for t, p, d, _ in emergency])
        self.assertEqual({priority for _, _, _, priority in emergency}, {3})

    def test_initial_battery_stress_sets_every_vehicle(self):
        sim = Simulation(seed=4, num_agents=6, strategy="B2", initial_battery=35)
        self.assertEqual([agent.battery for agent in sim.agents], [35.0] * 6)

    def test_stress_suite_covers_all_seven_scenarios(self):
        jobs = runner.make_jobs(runner.stress_experiments(), [1])
        labels = {job["x"] for job in jobs}
        self.assertEqual(labels, {"Normal", "High demand", "Multiple failures", "Blocked roads",
                                  "Low battery", "Emergency orders", "Large fleet"})
        by_label = {job["x"]: job for job in jobs}
        self.assertEqual(by_label["Emergency orders"]["task_priority"], 3)
        self.assertEqual(by_label["Low battery"]["initial_battery"], 35)
        self.assertEqual(by_label["Large fleet"]["num_agents"], 100)

    def test_deadline_suite_reports_deadline_metrics(self):
        jobs = runner.make_jobs(runner.deadline_experiments(), [1])
        self.assertEqual({job["experiment"] for job in jobs}, {"deadline_scenarios"})
        self.assertIn("on_time_rate", runner.METRICS)

    def test_auction_conflict_metrics_use_distinct_accept_claims(self):
        sim = Simulation(seed=9, num_agents=3, strategy="AUCTION")
        sim.bus.auction_history = [
            {"accepts": {1: 2.0}},
            {"accepts": {1: 4.0, 2: 3.5}},
            {"accepts": {}},
        ]
        result = summarize(sim)
        self.assertEqual(result["accepted_auctions"], 2)
        self.assertEqual(result["conflicted_auctions"], 1)
        self.assertEqual(result["unaccepted_auctions"], 1)
        self.assertEqual(result["auction_conflict_rate"], 0.5)

    def test_movement_and_charging_record_actual_energy(self):
        sim = Simulation(seed=14, num_agents=2, strategy="B1")
        agent = sim.agents[0]
        start = agent.position
        step_x = start[0] - 1 if start[0] > 0 else start[0] + 1
        agent._move_to((step_x, start[1]))
        self.assertEqual(agent.energy_used, config.ENERGY_PER_CELL)
        agent.battery = config.BATTERY_MAX - 2
        agent._charge()
        self.assertEqual(agent.energy_charged, 2)
        values = summarize(sim)
        self.assertEqual(values["energy_used"], config.ENERGY_PER_CELL)
        self.assertEqual(values["energy_charged"], 2)

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
