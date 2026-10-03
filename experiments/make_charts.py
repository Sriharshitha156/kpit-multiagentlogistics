"""
make_charts.py - draw Matplotlib charts from results/<suite>/summary.csv.

Usage:  python experiments/make_charts.py --suite main
Charts are saved in results/<suite>/charts/. Error bars show one standard deviation across seeds.
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLOURS = {"B1": "#8a96a3", "B2": "#3b82f6", "AUCTION": "#0fb39a"}
LABELS = {"B1": "B1 naive central", "B2": "B2 smart central", "AUCTION": "Auction (decentralized)"}

ALL = ["B1", "B2", "AUCTION"]
SMART = ["B2", "AUCTION"]
# experiment -> list of panels (metric, title, strategies)
PANELS = {
    "fleet_size": [("completed", "Tasks completed", ALL), ("avg_delivery", "Average delivery time (ticks)", ALL),
                   ("msgs_per_completed", "Messages per completed task", ["AUCTION"]), ("utilization", "Utilization", ALL)],
    "task_load": [("completion_rate", "Completion rate", ALL), ("avg_delivery", "Average delivery time (ticks)", ALL),
                  ("waiting", "Tasks still waiting at the end", ALL), ("utilization", "Utilization", ALL)],
    "obstacles": [("completion_rate", "Completion rate", ALL), ("avg_delivery", "Average delivery time (ticks)", ALL),
                  ("total_distance", "Total distance (cells)", ALL), ("battery_failures", "Vehicles that ran out of battery", ALL)],
    "failures": [("completion_rate", "Completion rate", ALL), ("lost", "Tasks lost at the end", ALL),
                 ("avg_delivery", "Average delivery time (ticks)", ALL), ("avg_reassign_time", "Reassignment time (ticks)", SMART)],
    "dispatcher_outage": [("completed", "Tasks completed", ALL), ("completion_rate", "Completion rate", ALL),
                          ("waiting", "Tasks still waiting at the end", ALL), ("avg_delivery", "Average delivery time (ticks)", ALL)],
    "message_loss": [("completion_rate", "Completion rate", SMART), ("avg_delivery", "Average delivery time (ticks)", SMART),
                     ("false_suspicions", "False failure alarms", ["AUCTION"]), ("messages_sent", "Messages sent", ["AUCTION"])],
    "timeout_sweep": [("false_suspicions", "False failure alarms", ["AUCTION"]),
                      ("avg_detection_latency", "Failure detection time (ticks)", ["AUCTION"]),
                      ("avg_delivery", "Average delivery time (ticks)", ["AUCTION"]),
                      ("completion_rate", "Completion rate", ["AUCTION"])],
}


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def number(value):
    return None if value in ("", None) else float(value)


def draw(rows, experiment, out_dir):
    rows = [r for r in rows if r["experiment"] == experiment]
    if not rows:
        return
    xs = []
    for r in rows:
        if r["x"] not in xs:
            xs.append(r["x"])
    try:
        positions = {x: float(x) for x in xs}
        numeric = True
    except ValueError:
        positions = {x: i for i, x in enumerate(xs)}
        numeric = False
    groups = sorted({r["group"] for r in rows})
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
    for ax, (metric, title, strategies) in zip(axes.flat, PANELS[experiment]):
        for strategy in strategies:
            for group in groups:
                pts = [r for r in rows if r["strategy"] == strategy and r["group"] == group and number(r[metric + "_mean"]) is not None]
                if not pts:
                    continue
                pts.sort(key=lambda r: positions[r["x"]])
                label = LABELS[strategy] + (" (loss %s)" % group if group else "")
                style = "-o" if numeric else "o"
                ax.errorbar([positions[r["x"]] for r in pts], [number(r[metric + "_mean"]) for r in pts],
                            yerr=[number(r[metric + "_std"]) or 0 for r in pts], fmt=style, capsize=3,
                            color=COLOURS[strategy], alpha=1.0 if not group else 0.35 + 0.3 * groups.index(group), label=label)
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.3)
        if not numeric:
            ax.set_xticks(list(positions.values()))
            ax.set_xticklabels(list(positions.keys()))
            ax.set_xlim(-0.5, len(xs) - 0.5)
        elif experiment == "fleet_size":
            ax.set_xscale("log")
            ax.set_xticks(list(positions.values()))
            ax.set_xticklabels([str(int(v)) for v in positions.values()])
    first = rows[0]
    for ax in axes[1]:
        ax.set_xlabel(xlabel(experiment))
    handles, labels = axes.flat[0].get_legend_handles_labels()
    if not handles:
        handles, labels = axes.flat[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("%s  (n = %s seeds per point, error bars = 1 std)" % (experiment.replace("_", " "), first["n"]), fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    os.makedirs(out_dir, exist_ok=True)
    fig.savefig(os.path.join(out_dir, experiment + ".png"), dpi=150)
    plt.close(fig)


def xlabel(experiment):
    return {"fleet_size": "Number of vehicles", "task_load": "Task spawn probability per tick",
            "obstacles": "Obstacle density", "failures": "Vehicles failed at tick 300",
            "dispatcher_outage": "Dispatcher outage at tick 300", "message_loss": "Message loss probability",
            "timeout_sweep": "Failure timeout (ticks)"}[experiment]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="main")
    args = parser.parse_args()
    suite_dir = os.path.join(ROOT, "results", args.suite)
    rows = read(os.path.join(suite_dir, "summary.csv"))
    for experiment in PANELS:
        draw(rows, experiment, os.path.join(suite_dir, "charts"))
    print("charts saved in", os.path.join(suite_dir, "charts"))


if __name__ == "__main__":
    main()
