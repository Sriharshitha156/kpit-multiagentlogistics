"""
config.py - every tunable number lives here.

If you want to change the map size, fleet size or battery behaviour,
change it HERE and nowhere else. Other files only read these values.
"""

# ---------- World ----------
GRID_WIDTH = 30             # number of cells horizontally
GRID_HEIGHT = 20            # number of cells vertically
OBSTACLE_DENSITY = 0.10     # fraction of cells that are blocked (0.10 = 10%)
OBSTACLE_EVENT_PROBABILITY = 0.0   # chance per tick that a NEW obstacle appears (0 = never)
NUM_CHARGERS = 3            # number of charging cells
RANDOM_SEED = 42            # same seed -> exactly the same map and behaviour

# ---------- Fleet ----------
NUM_AGENTS = 8
AGENT_SPEED = 1             # cells moved per tick
BATTERY_MAX = 100
ENERGY_PER_CELL = 1.0       # battery used for each cell moved
CHARGE_RATE = 5             # battery gained per tick while charging
CHARGE_TARGET = 90          # stop charging at this level
LOW_BATTERY = 45            # an idle agent below this goes to charge (tuned on seeds 1-5; use other seeds for experiments)
WANDER_WHEN_IDLE = False    # Phase 5 demo behaviour; False = idle agents wait where they are

# ---------- Tasks ----------
TASK_SPAWN_PROBABILITY = 0.08   # chance per tick that a new delivery request appears
MAX_OPEN_TASKS = 30             # safety cap so the screen never floods with waiting tasks
MINUTES_PER_TICK = 1            # illustrative time scale; not calibrated to a real fleet
DELIVERY_DEADLINE_MINUTES = 90  # default promised delivery window in simulated minutes

# ---------- Which allocation strategy runs ----------
STRATEGY = "AUCTION"        # "B1" central nearest-idle | "B2" central with our cost + battery rule | "AUCTION" decentralized

# ---------- Bidding (used by auction agents AND by baseline B2) ----------
W_TIME = 1.0                # weight of estimated time in the bid cost
W_LOAD = 5.0                # weight of how many tasks the agent already holds
PRIORITY_FACTOR = {1: 0.5, 2: 1.0, 3: 2.0}   # urgent tasks make waiting time count more
SAFETY_MARGIN = 0.20        # extra battery buffer in the feasibility check
MAX_QUEUE = 3               # maximum tasks an agent may hold at once

# ---------- Auction timing and the simulated network ----------
MESSAGE_DELAY = 1           # ticks a message takes to arrive
HEARTBEAT_INTERVAL = 3      # ticks between an agent's "I am alive" messages
FAILURE_TIMEOUT = 15        # silent ticks before a peer is declared dead (chosen from the timeout sweep on tuning seeds 2001-2005; must exceed interval + delay)
BID_WINDOW = 2              # ticks an auction collects bids (must be LARGER than MESSAGE_DELAY)
ACCEPT_GRACE = 3            # ticks to wait for the winner's TASK_ACCEPT before re-auctioning
RETRY_INTERVAL = 10         # ticks before re-auctioning a task that got no bids
LOSS_PROBABILITY = 0.0      # chance that any single message is lost (raised in experiments)

# ---------- Display (Pygame) ----------
CELL_SIZE = 26              # pixels per grid cell
PANEL_WIDTH = 300           # width of the information panel on the right
TICKS_PER_SECOND = 8        # simulation speed (UP/DOWN keys change it live)
FPS = 60                    # screen refresh rate
