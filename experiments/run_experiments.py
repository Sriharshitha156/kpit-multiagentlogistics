"""
run_experiments.py - headless batch experiments (no window).

Every number in the results comes from running the simulator. The paired-* suites
replay the same precomputed delivery requests to each strategy, then report the mean
and spread across seeds.

Usage (from the project folder):
    python experiments/run_experiments.py --suite paired-sweep  # failure-timeout vs message-loss sweep
    python experiments/run_experiments.py --suite paired-main   # main paired comparison
    python experiments/run_experiments.py --suite paired-quick  # tiny paired smoke run

Results are written to results/<suite>/ : raw_runs.csv, summary.csv, settings.json.
A run can be stopped and restarted: finished runs are skipped.
"""

import argparse
import csv
import json
import os
import random
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config                      # noqa: E402
from metrics import summarize      # noqa: E402
from simulation import Simulation  # noqa: E402

STRATEGIES = ["B1", "B2", "AUCTION"]
FAIL_TICK = 300                    # failures and outages start at this tick
MAIN_SEEDS = list(range(1001, 1011))     # fresh test seeds (never used while tuning)
SWEEP_SEEDS = list(range(2001, 2006))    # tuning seeds, used only for the timeout sweep
QUICK_SEEDS = [1, 2]
SCALE_SEEDS = [3001, 3002, 3003]

METRICS = ["created", "completed", "completion_rate", "lost", "waiting", "avg_delivery", "reassigned",
           "avg_reassign_time", "avg_detection_latency", "false_suspicions", "battery_failures",
           "failed_agents", "utilization", "total_distance", "messages_sent", "messages_delivered",
           "heartbeat_sent", "msgs_per_completed"]
KEY_FIELDS = ["experiment", "group", "x", "strategy", "seed"]


def exp(name, x_name, xs, build, strategies=STRATEGIES, groups=("",)):
    """Describe one experiment. `build(x, group)` returns the settings for one scenario."""
    return {"name": name, "x_name": x_name, "xs": xs, "build": build, "strategies": strategies, "groups": groups}


def scenario(num_agents=8, overrides=None, failures=0, outage=False, task_count=None):
    return {"num_agents": num_agents, "overrides": overrides or {}, "failures": failures,
            "outage": outage, "task_count": task_count}


def main_experiments():
    return [
        exp("fleet_size", "agents", [5, 10, 20, 50], lambda x, g: scenario(num_agents=x)),
        exp("task_load", "task spawn probability", [0.04, 0.08, 0.15],
            lambda x, g: scenario(overrides={"TASK_SPAWN_PROBABILITY": x})),
        exp("obstacles", "obstacle density", [0.0, 0.10, 0.20],
            lambda x, g: scenario(overrides={"OBSTACLE_DENSITY": x})),
        exp("failures", "agents failed at tick %d" % FAIL_TICK, [0, 1, 2, 4],
            lambda x, g: scenario(failures=x)),
        exp("dispatcher_outage", "dispatcher outage at tick %d" % FAIL_TICK, ["no", "yes"],
            lambda x, g: scenario(outage=(x == "yes"))),
        exp("message_loss", "message loss probability", [0.0, 0.05, 0.10, 0.20],
            lambda x, g: scenario(overrides={"LOSS_PROBABILITY": x}, failures=2)),
    ]


def sweep_experiments():
    return [exp("timeout_sweep", "failure timeout (ticks)", [7, 10, 15, 20, 30],
                lambda x, g: scenario(overrides={"FAILURE_TIMEOUT": x, "LOSS_PROBABILITY": float(g)}, failures=2),
                strategies=["AUCTION"], groups=("0.0", "0.1", "0.2"))]


def quick_experiments():
    return [exp("fleet_size", "agents", [5, 10], lambda x, g: scenario(num_agents=x)),
            exp("failures", "agents failed", [0, 1], lambda x, g: scenario(failures=x))]


def scale_experiments():
    """Bounded scalability checks with fixed order counts and explicit recovery stress."""
    return [
        exp("scale_agents", "agents", [5, 10, 25, 50, 100],
            lambda x, g: scenario(num_agents=x, failures=max(1, (x + 9) // 10), task_count=50)),
        exp("scale_tasks", "orders", [25, 50, 100],
            lambda x, g: scenario(num_agents=25, failures=2, task_count=x)),
        exp("scale_obstacles", "obstacle density", [0.0, 0.10, 0.20],
            lambda x, g: scenario(num_agents=25, failures=2, task_count=50,
                                  overrides={"OBSTACLE_DENSITY": x})),
    ]


SUITES = {"main": (main_experiments, MAIN_SEEDS, 1500),
          "sweep": (sweep_experiments, SWEEP_SEEDS, 1500),
          "quick": (quick_experiments, QUICK_SEEDS, 500),
          # New output directories keep old, unpaired CSV results from being reused.
          "paired-main": (main_experiments, MAIN_SEEDS, 1500),
          "paired-sweep": (sweep_experiments, SWEEP_SEEDS, 1500),
          "paired-quick": (quick_experiments, QUICK_SEEDS, 500),
          "paired-scale": (scale_experiments, SCALE_SEEDS, 600),
          # Fresh folder for a clean, reviewable result set, separate from prior runs.
          "paired-scale-clean": (scale_experiments, SCALE_SEEDS, 600)}


def make_jobs(experiments, seeds):
    jobs = []
    for e in experiments:
        for group in e["groups"]:
            for x in e["xs"]:
                for strategy in e["strategies"]:
                    for seed in seeds:
                        job = dict(e["build"](x, group))
                        job.update({"experiment": e["name"], "group": group, "x": x,
                                    "strategy": strategy, "seed": seed})
                        jobs.append(job)
    return jobs


def failing_agents(seed, num_agents, count):
    """Which agents fail. Depends only on the seed, so every strategy sees the SAME failures."""
    return random.Random(seed * 100 + count).sample(range(1, num_agents + 1), count)


def build_task_schedule(seed, ticks, spawn_probability, task_count=None):
    """Create exogenous task arrivals once so paired strategies get identical demand."""
    from environment import Environment

    arrivals = random.Random(seed + 99173)
    template = Environment(seed)
    counts_by_tick = {}
    if task_count is not None:
        for _ in range(task_count):
            tick = arrivals.randrange(1, ticks + 1)
            counts_by_tick[tick] = counts_by_tick.get(tick, 0) + 1
    schedule = []
    for tick in range(1, ticks + 1):
        count = counts_by_tick.get(tick, 0) if task_count is not None else int(arrivals.random() < spawn_probability)
        for _ in range(count):
            task = template.spawn_task(tick)
            schedule.append((tick, task.pickup, task.destination, task.priority))
    return schedule


def run_job(job, ticks):
    """Run one simulation and return its row of metrics."""
    saved = {k: getattr(config, k) for k in job["overrides"]}
    for key, value in job["overrides"].items():
        setattr(config, key, value)
    try:
        paired = job.get("paired_tasks", False)
        task_schedule = (build_task_schedule(job["seed"], ticks, config.TASK_SPAWN_PROBABILITY,
                                             job.get("task_count"))
                         if paired else None)
        compute_started = time.perf_counter()
        sim = Simulation(seed=job["seed"], num_agents=job["num_agents"], strategy=job["strategy"],
                         task_schedule=task_schedule)
        doomed = failing_agents(job["seed"], job["num_agents"], job["failures"])
        for t in range(ticks):
            if t == FAIL_TICK:
                for agent_id in doomed:
                    sim.fail_agent(agent_id)
                if job["outage"] and sim.dispatcher is not None:
                    sim.dispatcher.online = False
            sim.step()
        m = summarize(sim)
        compute_seconds = time.perf_counter() - compute_started
    finally:
        for key, value in saved.items():
            setattr(config, key, value)

    row = {k: job[k] for k in KEY_FIELDS}
    row.update({
        "created": m["created"], "completed": m["completed"],
        "completion_rate": m["completed"] / m["created"] if m["created"] else None,
        "lost": m["lost"], "waiting": m["waiting"], "avg_delivery": m["average_delivery_time"],
        "reassigned": m["reassigned_tasks"], "avg_reassign_time": m["avg_reassignment_time"],
        "avg_detection_latency": m["avg_detection_latency"], "false_suspicions": m["false_suspicions"],
        "battery_failures": m["battery_failures"], "failed_agents": m["failed_agents"],
        "utilization": m["utilization"], "total_distance": m["total_distance"],
        "messages_sent": m["messages_sent"], "messages_delivered": m["messages_delivered"],
        "heartbeat_sent": m["messages_by_type"].get("HEARTBEAT", 0),
        "msgs_per_completed": m["messages_per_completed_task"],
    })
    if job.get("track_runtime"):
        row["compute_seconds"] = compute_seconds
    return row


def job_key(row_or_job):
    return tuple(str(row_or_job[k]) for k in KEY_FIELDS)


def read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def aggregate(rows, metrics=METRICS):
    """Mean and standard deviation over seeds for every (experiment, group, strategy, x)."""
    buckets = {}
    for row in rows:
        buckets.setdefault((row["experiment"], row["group"], row["strategy"], str(row["x"])), []).append(row)
    summary = []
    for (experiment, group, strategy, x), items in buckets.items():
        out = {"experiment": experiment, "group": group, "x": x, "strategy": strategy, "n": len(items)}
        for metric in metrics:
            values = [float(r[metric]) for r in items if r[metric] not in ("", None)]
            out[metric + "_mean"] = statistics.mean(values) if values else ""
            out[metric + "_std"] = statistics.stdev(values) if len(values) > 1 else (0.0 if values else "")
        summary.append(out)
    return summary


def write_csv(path, rows, fields):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=list(SUITES), default="quick")
    parser.add_argument("--ticks", type=int, default=None, help="override the number of ticks per run")
    args = parser.parse_args()

    builder, seeds, default_ticks = SUITES[args.suite]
    ticks = args.ticks or default_ticks
    out_dir = os.path.join(ROOT, "results", args.suite)
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw_runs.csv")

    jobs = make_jobs(builder(), seeds)
    if args.suite.startswith("paired-"):
        for job in jobs:
            job["paired_tasks"] = True
            if args.suite.startswith("paired-scale"):
                job["track_runtime"] = True
    done = {job_key(r) for r in read_rows(raw_path)}
    todo = [j for j in jobs if job_key(j) not in done]
    print("suite=%s  ticks=%d  seeds=%d  runs: %d total, %d already done" % (args.suite, ticks, len(seeds), len(jobs), len(done)))

    with open(os.path.join(out_dir, "settings.json"), "w") as f:
        json.dump({"suite": args.suite, "ticks": ticks, "seeds": seeds, "fail_tick": FAIL_TICK,
                   "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "task_schedule": "precomputed and replayed per seed and scenario" if args.suite.startswith("paired-") else "live random arrivals",
                   "fixed_task_counts": args.suite.startswith("paired-scale"),
                   "config": {k: getattr(config, k) for k in dir(config) if k.isupper() and k != "PRIORITY_FACTOR"}}, f, indent=2)

    report_metrics = METRICS + (["compute_seconds"] if args.suite.startswith("paired-scale") else [])
    fields = KEY_FIELDS + report_metrics
    new_file = not os.path.exists(raw_path)
    start = time.time()
    with open(raw_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        for i, job in enumerate(todo, 1):
            writer.writerow(run_job(job, ticks))
            f.flush()
            if i % 10 == 0 or i == len(todo):
                print("  %d / %d runs  (%.0f s)" % (i, len(todo), time.time() - start), flush=True)

    summary = aggregate(read_rows(raw_path), report_metrics)
    summary_fields = ["experiment", "group", "x", "strategy", "n"] + [m + s for m in report_metrics for s in ("_mean", "_std")]
    write_csv(os.path.join(out_dir, "summary.csv"), summary, summary_fields)
    print("done. wrote", raw_path, "and summary.csv")


if __name__ == "__main__":
    main()
