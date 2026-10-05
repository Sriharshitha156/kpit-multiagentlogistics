"""
task.py - Task (ground truth) and TaskInfo (what agents are allowed to know).

DESIGN RULE: a Task object is the world's "ground truth". Only the environment
and the metrics code use it. Agents only ever receive a TaskInfo: a plain copy
of the task's description, carried inside messages.
"""

# Task statuses (the lifecycle: OPEN -> ASSIGNED -> PICKED_UP -> COMPLETED)
OPEN = "OPEN"
ASSIGNED = "ASSIGNED"
PICKED_UP = "PICKED_UP"
COMPLETED = "COMPLETED"
LOST = "LOST"            # unfinished at the end of a run

# Priorities
LOW = 1
MEDIUM = 2
HIGH = 3


class TaskInfo:
    """A plain description of a delivery. This is what travels inside messages."""

    def __init__(self, task_id, pickup, destination, priority, created_tick):
        self.task_id = task_id
        self.pickup = pickup                  # (x, y) cell
        self.destination = destination        # (x, y) cell
        self.priority = priority              # LOW, MEDIUM or HIGH
        self.created_tick = created_tick


class Task:
    """One delivery: pick a parcel up at `pickup` and drop it at `destination`."""

    def __init__(self, task_id, pickup, destination, priority, created_tick):
        self.task_id = task_id
        self.pickup = pickup
        self.destination = destination
        self.priority = priority
        self.created_tick = created_tick
        self.status = OPEN
        self.owner_id = None                  # which agent owns it (for metrics only)
        self.epoch = 1                        # goes up each time the task is re-auctioned
        self.parcel_position = pickup         # changes if a carrier fails (Phase 9)
        self.reassign_count = 0
        self.picked_up_tick = None
        self.completed_tick = None
        self.orphaned_by = None
        self.orphaned_tick = None
        self.recovery_events = []      # failure, reassignment, rescue approach distance, and outcome

    def describe(self):
        """Make the plain copy that can be sent to agents."""
        return TaskInfo(self.task_id, self.pickup, self.destination, self.priority, self.created_tick)
