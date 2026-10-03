"""
scenarios.py - one-key demo presets.

Every preset works on a LIST of simulations: one in normal mode, two in split-screen mode.
That way both simulations receive exactly the same event, so the comparison stays fair.
"""

import random

import config


def rush_hour(sims, count=12):
    """A burst of new delivery orders arrives at once."""
    created = 0
    for _ in range(count):
        if any(sim.env.open_task_count() >= config.MAX_OPEN_TASKS for sim in sims):
            break
        for sim in sims:
            sim.new_task()
        created += 1
    return "Rush hour: %d new orders" % created


def failure_storm(sims, count=3, rng=None):
    """Several vehicles fail at the same moment (at least one always survives)."""
    rng = rng or random.Random()
    alive = [a.agent_id for a in sims[0].agents if a.is_alive()]
    victims = rng.sample(alive, max(0, min(count, len(alive) - 1)))
    for agent_id in victims:
        for sim in sims:
            sim.fail_agent(agent_id)
    return "Failure storm: vehicles %s failed" % (", ".join("A%d" % v for v in sorted(victims)) or "none")


def blocked_road(sims, count=12):
    """Roads get blocked. The first simulation picks the cells and the others copy them."""
    blocked = 0
    for _ in range(count):
        cell = sims[0].add_obstacle()
        if cell is None:
            continue
        blocked += 1
        for sim in sims[1:]:
            sim.add_obstacle(cell)
    return "Blocked road: %d cells blocked" % blocked
