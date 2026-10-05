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


def failure_recovery_demo(sims):
    """Create a repeatable task, let agents allocate it, then fail its carrier."""
    previous_spawn_probability = config.TASK_SPAWN_PROBABILITY
    config.TASK_SPAWN_PROBABILITY = 0.0
    owners = []
    try:
        for sim in sims:
            carrier = sim.agents[0]
            pickup = carrier.position
            destinations = []
            for x in range(sim.env.width):
                for y in range(sim.env.height):
                    cell = (x, y)
                    if not sim.env.is_free(cell) or cell == pickup or cell in sim.env.chargers:
                        continue
                    delivery_distance = carrier.path_length(pickup, cell, sim.env)
                    charger_distances = [carrier.path_length(cell, charger, sim.env)
                                         for charger in sim.env.chargers]
                    charger_distances = [distance for distance in charger_distances if distance is not None]
                    if delivery_distance is None or not charger_distances:
                        continue
                    energy_needed = (delivery_distance + min(charger_distances)) * config.ENERGY_PER_CELL
                    if carrier.battery >= energy_needed * (1 + config.SAFETY_MARGIN):
                        destinations.append((delivery_distance, cell))
            if not destinations:
                raise RuntimeError("no battery-feasible destination for the recovery demo")
            _, destination = max(destinations, key=lambda item: (item[0], item[1]))
            task = sim.new_task(pickup=pickup, destination=destination, priority=3)

            for _ in range(100):
                sim.step()
                if task.status == "PICKED_UP":
                    break
            else:
                raise RuntimeError("recovery demo task was not picked up")

            owner_id = task.owner_id
            sim.fail_agent(owner_id)
            owners.append(owner_id)
    finally:
        config.TASK_SPAWN_PROBABILITY = previous_spawn_probability

    task_ids = sorted({task.task_id for sim in sims for task in sim.env.tasks
                       if task.owner_id in owners})
    owner_labels = ", ".join("A%d" % owner for owner in sorted(set(owners)))
    task_labels = ", ".join("#%d" % task_id for task_id in task_ids)
    return "Recovery demo: %s failed carrying task %s; watch for detection and re-auction" % (
        owner_labels, task_labels)
