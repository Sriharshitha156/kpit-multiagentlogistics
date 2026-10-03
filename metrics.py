"""
metrics.py - numbers computed from what actually happened in the simulation.
We never type in results by hand: everything below is calculated.
"""

from agent import FAILED
from task import ASSIGNED, COMPLETED, OPEN, PICKED_UP


def summarize(sim):
    """Return a dictionary of the current metrics."""
    env = sim.env
    tasks = sim.env.tasks
    failed_ids = {a.agent_id for a in sim.agents if a.status == FAILED}

    completed = [t for t in tasks if t.status == COMPLETED]
    # A task is "lost" if its owner failed and nobody took it over (recovery comes in Phase 9).
    lost = [t for t in tasks if t.status in (ASSIGNED, PICKED_UP) and t.owner_id in failed_ids]
    in_progress = [t for t in tasks if t.status in (ASSIGNED, PICKED_UP) and t.owner_id not in failed_ids]
    waiting = [t for t in tasks if t.status == OPEN]

    if completed:
        average_delivery_time = sum(t.completed_tick - t.created_tick for t in completed) / len(completed)
    else:
        average_delivery_time = None

    alive_ticks = sum(a.alive_ticks for a in sim.agents)
    busy_ticks = sum(a.busy_ticks for a in sim.agents)

    messages_sent = sim.bus.messages_sent if sim.bus is not None else 0
    messages_delivered = sim.bus.messages_delivered if sim.bus is not None else 0

    return {
        "created": len(tasks),
        "completed": len(completed),
        "lost": len(lost),
        "in_progress": len(in_progress),
        "waiting": len(waiting),
        "average_delivery_time": average_delivery_time,
        "total_distance": sum(a.distance_travelled for a in sim.agents),
        "failed_agents": len(failed_ids),
        "battery_failures": sum(1 for a in sim.agents if a.fail_reason == "BATTERY"),
        "utilization": (busy_ticks / alive_ticks) if alive_ticks else 0.0,
        "reassigned_tasks": sum(1 for t in tasks if t.reassign_count > 0),
        "avg_reassignment_time": (sum(env.reassignment_times) / len(env.reassignment_times)) if env.reassignment_times else None,
        "avg_detection_latency": (sum(env.detection_ticks[a] - env.failure_ticks[a] for a in env.detection_ticks) / len(env.detection_ticks)) if env.detection_ticks else None,
        "false_suspicions": env.false_suspicions,
        "messages_by_type": dict(sim.bus.sent_by_type) if sim.bus is not None else {},
        "messages_sent": messages_sent,
        "messages_delivered": messages_delivered,
        "messages_per_completed_task": (messages_sent / len(completed)) if completed else None,
    }
