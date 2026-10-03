"""
environment.py - the world: grid, obstacles, chargers and delivery requests.

The Environment knows the TRUE map. It answers questions like
"is this cell free?" and creates new delivery tasks.
"""

import random

import config
from task import Task


def manhattan(a, b):
    """Grid distance ignoring obstacles: |dx| + |dy|. (Replaced by A* path length in Phase 8.)"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Environment:
    """A 2D grid world. Cells are (x, y) tuples, (0, 0) is the top-left corner."""

    def __init__(self, seed=config.RANDOM_SEED):
        # One random generator for the whole world. Using a fixed seed makes
        # every run repeatable, which we need for fair experiments later.
        self.rng = random.Random(seed)
        self.width = config.GRID_WIDTH
        self.height = config.GRID_HEIGHT
        self.obstacles = set()     # set of blocked cells
        self.chargers = []         # list of charging cells
        self.tasks = []            # all tasks created so far (ground truth)
        self.task_by_id = {}       # quick lookup: task_id -> Task
        # ground truth about failures, used ONLY by the metrics (agents never read these)
        self.failure_ticks = {}        # agent_id -> tick it really failed
        self.detection_ticks = {}      # agent_id -> tick the first peer noticed
        self.reassignment_times = []   # ticks from an owner's failure to a new owner's accept
        self.false_suspicions = 0      # a living agent was declared dead
        self.next_task_id = 1
        self._place_chargers()
        self._place_obstacles()

    # ----- map building -----
    def _place_chargers(self):
        """Pick NUM_CHARGERS different random cells as charging stations."""
        while len(self.chargers) < config.NUM_CHARGERS:
            cell = (self.rng.randrange(self.width), self.rng.randrange(self.height))
            if cell not in self.chargers:
                self.chargers.append(cell)

    def _place_obstacles(self):
        """
        Block a fraction of the cells. Never a charger cell, and never a cell that
        would cut the free map into separate pieces (so every task stays reachable).
        """
        wanted = int(self.width * self.height * config.OBSTACLE_DENSITY)
        attempts = 0
        while len(self.obstacles) < wanted and attempts < wanted * 30:
            attempts += 1
            cell = (self.rng.randrange(self.width), self.rng.randrange(self.height))
            if cell in self.chargers or cell in self.obstacles:
                continue
            if self._is_connected(self.obstacles | {cell}):
                self.obstacles.add(cell)

    def _is_connected(self, blocked):
        """True if all free cells can reach each other (checked with a flood fill)."""
        free = [(x, y) for x in range(self.width) for y in range(self.height) if (x, y) not in blocked]
        if not free:
            return False
        seen = {free[0]}
        stack = [free[0]]
        while stack:
            x, y = stack.pop()
            for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (0 <= neighbour[0] < self.width and 0 <= neighbour[1] < self.height
                        and neighbour not in blocked and neighbour not in seen):
                    seen.add(neighbour)
                    stack.append(neighbour)
        return len(seen) == len(free)

    def add_obstacle(self, cell, protected=()):
        """
        Block one more cell while the simulation is running (a "changing condition").
        Refused if the cell is a charger, is in `protected`, or would split the map.
        """
        if not self.is_free(cell) or cell in self.chargers or cell in protected:
            return False
        if not self._is_connected(self.obstacles | {cell}):
            return False
        self.obstacles.add(cell)
        return True

    # ----- questions about the map -----
    def in_bounds(self, cell):
        """True if the cell is inside the grid."""
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def is_free(self, cell):
        """True if an agent can stand on this cell."""
        return self.in_bounds(cell) and cell not in self.obstacles

    def free_neighbors(self, cell):
        """The free cells directly above, below, left and right of `cell`."""
        x, y = cell
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [c for c in candidates if self.is_free(c)]

    def random_free_cell(self, avoid_chargers=False):
        """Pick a random cell that is not an obstacle."""
        while True:
            cell = (self.rng.randrange(self.width), self.rng.randrange(self.height))
            if self.is_free(cell) and not (avoid_chargers and cell in self.chargers):
                return cell

    def nearest_charger(self, cell):
        """The closest charger by Manhattan distance (|dx| + |dy|)."""
        return min(self.chargers, key=lambda c: abs(c[0] - cell[0]) + abs(c[1] - cell[1]))

    # ----- delivery requests -----
    def spawn_task(self, current_tick):
        """Create a new delivery task with a random pickup, destination and priority."""
        pickup = self.random_free_cell(avoid_chargers=True)
        destination = self.random_free_cell(avoid_chargers=True)
        while destination == pickup:
            destination = self.random_free_cell(avoid_chargers=True)
        priority = self.rng.choice([1, 2, 3])
        task = Task(self.next_task_id, pickup, destination, priority, current_tick)
        self.next_task_id += 1
        self.add_task(task)
        return task

    def add_task(self, task):
        """Register a task in the world."""
        self.tasks.append(task)
        self.task_by_id[task.task_id] = task

    # ----- "world events": agents call these when they physically act -----
    # These only update the ground truth used by the metrics and the drawing.
    # Agents NEVER read this information back. They learn about each other through messages.
    def record_assignment(self, task_id, agent_id, tick):
        task = self.task_by_id[task_id]
        if task.status == "COMPLETED":
            return
        previous = task.owner_id
        if previous is not None and previous != agent_id and previous in self.failure_ticks:
            task.reassign_count += 1                                  # a task was recovered
            self.reassignment_times.append(tick - self.failure_ticks[previous])
        task.status = "ASSIGNED"
        task.owner_id = agent_id

    def record_detection(self, failed_id, tick):
        """A peer declared `failed_id` dead. Count the first real detection, and any false alarm."""
        if failed_id not in self.failure_ticks:
            self.false_suspicions += 1
        elif failed_id not in self.detection_ticks:
            self.detection_ticks[failed_id] = tick

    def record_pickup(self, task_id, tick):
        task = self.task_by_id[task_id]
        task.status = "PICKED_UP"
        task.picked_up_tick = tick

    def record_delivery(self, task_id, tick):
        task = self.task_by_id[task_id]
        if task.status == "COMPLETED":
            return
        task.status = "COMPLETED"
        task.completed_tick = tick

    def open_task_count(self):
        """How many tasks are still waiting for an owner."""
        return sum(1 for t in self.tasks if t.status == "OPEN")
