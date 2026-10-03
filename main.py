"""
main.py - the Pygame window. Run with:   python main.py          (add --split to start in split-screen)

Keys:  SPACE pause | UP/DOWN speed | R new map | TAB switch strategy | S split screen
       1 rush hour | 2 failure storm | 3 blocked road | D dispatcher on/off | H heartbeats in feed
Mouse: click a vehicle to fail it | right-click a cell to block it | ESC quit
In split-screen both worlds are identical and every event happens in both.
"""

import random
import sys

import pygame

import config
import scenarios
from agent import CHARGING, DELIVERING, FAILED, GOING_TO_CHARGE, GOING_TO_PICKUP
from communication import HEARTBEAT, describe_message
from metrics import summarize
from simulation import Simulation
from task import ASSIGNED, COMPLETED, OPEN

# ---------- colours ----------
BG = (10, 26, 43)
GRID_LINE = (24, 48, 74)
OBSTACLE = (70, 82, 96)
CHARGER = (30, 150, 90)
PANEL_BG = (14, 34, 54)
FEED_BG = (7, 18, 30)
TEXT = (235, 240, 245)
MUTED = (150, 170, 190)
RED = (255, 92, 92)
YELLOW = (255, 210, 60)
GREEN = (60, 200, 120)
TEAL = (25, 195, 169)
DEST_BLUE = (90, 170, 255)
PRIORITY_COLOURS = {1: (130, 150, 175), 2: (255, 190, 60), 3: (255, 120, 70)}
AGENT_COLOURS = [(25, 195, 169), (255, 140, 90), (120, 160, 255), (240, 120, 200),
                 (170, 220, 90), (255, 220, 100), (180, 130, 255), (100, 220, 230)]
FEED_COLOURS = {"TASK_REQUEST": TEXT, "TASK_BID": MUTED, "TASK_ACCEPT": TEAL, "DELIVERY_COMPLETE": GREEN,
                "TASK_REASSIGN": YELLOW, "AGENT_FAILURE": RED, "HEARTBEAT": (90, 110, 130)}

STRATEGIES = ["B1", "B2", "AUCTION"]
STRATEGY_LABELS = {"B1": "B1 central, nearest idle", "B2": "B2 central, same cost + battery rule",
                   "AUCTION": "Auction (decentralized)"}

FEED_HEIGHT = 120
SINGLE_SIZE = (config.GRID_WIDTH * config.CELL_SIZE + config.PANEL_WIDTH, config.GRID_HEIGHT * config.CELL_SIZE + FEED_HEIGHT)
SPLIT_CELL = 20
SPLIT_SIZE = (1240, 680)


class View:
    """Where a grid is drawn on the screen and how big its cells are."""

    def __init__(self, origin_x, origin_y, cell):
        self.ox, self.oy, self.cell = origin_x, origin_y, cell

    def center(self, cell):
        return (self.ox + cell[0] * self.cell + self.cell // 2, self.oy + cell[1] * self.cell + self.cell // 2)

    def width(self):
        return config.GRID_WIDTH * self.cell

    def height(self):
        return config.GRID_HEIGHT * self.cell

    def pixel_to_cell(self, pos):
        """The grid cell under a mouse position, or None if the mouse is outside this grid."""
        x, y = pos[0] - self.ox, pos[1] - self.oy
        if 0 <= x < self.width() and 0 <= y < self.height():
            return (x // self.cell, y // self.cell)
        return None


def agent_colour(agent):
    return AGENT_COLOURS[(agent.agent_id - 1) % len(AGENT_COLOURS)]


def draw_text(screen, font, text, x, y, colour=TEXT):
    screen.blit(font.render(text, True, colour), (x, y))


# ---------- drawing the world ----------
def draw_grid(screen, sim, view):
    c = view.cell
    for x in range(config.GRID_WIDTH + 1):
        pygame.draw.line(screen, GRID_LINE, (view.ox + x * c, view.oy), (view.ox + x * c, view.oy + view.height()))
    for y in range(config.GRID_HEIGHT + 1):
        pygame.draw.line(screen, GRID_LINE, (view.ox, view.oy + y * c), (view.ox + view.width(), view.oy + y * c))
    for (x, y) in sim.env.obstacles:
        pygame.draw.rect(screen, OBSTACLE, (view.ox + x * c + 1, view.oy + y * c + 1, c - 1, c - 1))
    for (x, y) in sim.env.chargers:
        pygame.draw.rect(screen, CHARGER, (view.ox + x * c + 3, view.oy + y * c + 3, c - 5, c - 5), border_radius=4)


def draw_tasks(screen, sim, view, small_font):
    """Pickup = square (colour = priority). Destination = ring. Red = owner failed, task is orphaned."""
    failed_ids = {a.agent_id for a in sim.agents if a.status == FAILED}
    for task in sim.env.tasks:
        if task.status == COMPLETED:
            continue
        orphaned = task.owner_id in failed_ids
        dest = view.center(task.destination)
        if task.status in (OPEN, ASSIGNED):
            pickup = view.center(task.pickup)
            pygame.draw.line(screen, (45, 80, 115), pickup, dest, 1)
            half = max(3, view.cell // 4)
            colour = RED if orphaned else PRIORITY_COLOURS[task.priority]
            pygame.draw.rect(screen, colour, (pickup[0] - half, pickup[1] - half, half * 2, half * 2))
        pygame.draw.circle(screen, RED if orphaned else DEST_BLUE, dest, max(3, view.cell // 4), 2)
        label = small_font.render(str(task.task_id), True, TEXT)
        screen.blit(label, (dest[0] + 5, dest[1] - 12))


def draw_routes(screen, sim, view):
    """The real A* route of each working agent."""
    for agent in sim.agents:
        if not agent.is_alive():
            continue
        target, colour = None, agent_colour(agent)
        if agent.status == GOING_TO_PICKUP:
            target = agent.assigned_task.pickup
        elif agent.status == DELIVERING:
            target = agent.assigned_task.destination
        elif agent.status == GOING_TO_CHARGE:
            target, colour = agent.charger_target, YELLOW
        if target is None:
            continue
        if agent.path:
            points = [view.center(agent.position)] + [view.center(c) for c in agent.path]
            pygame.draw.lines(screen, colour, False, points, 2)
        else:
            pygame.draw.line(screen, colour, view.center(agent.position), view.center(target), 1)


def draw_agents(screen, sim, view, small_font):
    c = view.cell
    for agent in sim.agents:
        cx, cy = view.center(agent.position)
        radius = c // 2 - 3
        if agent.status == FAILED:
            pygame.draw.circle(screen, (90, 90, 100), (cx, cy), radius)
            d = max(4, c // 4)
            pygame.draw.line(screen, RED, (cx - d, cy - d), (cx + d, cy + d), 3)
            pygame.draw.line(screen, RED, (cx - d, cy + d), (cx + d, cy - d), 3)
            continue
        pygame.draw.circle(screen, agent_colour(agent), (cx, cy), radius)
        if agent.status == CHARGING:
            pygame.draw.circle(screen, YELLOW, (cx, cy), radius + 2, 2)
        if agent.status == DELIVERING:
            pygame.draw.circle(screen, TEXT, (cx, cy), radius + 2, 2)       # white ring = carrying a parcel
        label = small_font.render(str(agent.agent_id), True, (10, 20, 30))
        screen.blit(label, label.get_rect(center=(cx, cy)))
        bar_w = c - 6
        fill = int(bar_w * agent.battery / config.BATTERY_MAX)
        bar_colour = GREEN if agent.battery > 50 else (YELLOW if agent.battery > config.LOW_BATTERY else RED)
        pygame.draw.rect(screen, (30, 40, 55), (cx - bar_w // 2, cy - c // 2 - 1, bar_w, 4))
        pygame.draw.rect(screen, bar_colour, (cx - bar_w // 2, cy - c // 2 - 1, fill, 4))


def draw_world(screen, sim, view, small_font):
    draw_grid(screen, sim, view)
    draw_tasks(screen, sim, view, small_font)
    draw_routes(screen, sim, view)
    draw_agents(screen, sim, view, small_font)


# ---------- text blocks ----------
def metric_texts(sim):
    m = summarize(sim)
    avg = "-" if m["average_delivery_time"] is None else "%.1f ticks" % m["average_delivery_time"]
    reassign = "-" if m["avg_reassignment_time"] is None else "%.1f ticks" % m["avg_reassignment_time"]
    if sim.dispatcher is None:
        dispatcher, dispatcher_colour = "none (decentralized)", GREEN
    else:
        dispatcher = "ONLINE" if sim.dispatcher.online else "OFFLINE"
        dispatcher_colour = GREEN if sim.dispatcher.online else RED
    if sim.bus is None:
        messages = "- (central)"
    else:
        messages = "%d sent, %d recv" % (sim.bus.messages_sent, sim.bus.messages_delivered)
    return m, avg, reassign, dispatcher, dispatcher_colour, messages


def draw_panel(screen, sim, fonts, ticks_per_second, paused):
    """Right-hand panel of the single view: live metrics, agent list, legend, keys."""
    font, small_font, title_font = fonts[0], fonts[1], fonts[2]
    m, avg, reassign, dispatcher, dispatcher_colour, messages = metric_texts(sim)
    px = config.GRID_WIDTH * config.CELL_SIZE
    pygame.draw.rect(screen, PANEL_BG, (px, 0, config.PANEL_WIDTH, config.GRID_HEIGHT * config.CELL_SIZE))
    x = px + 14
    draw_text(screen, title_font, "Smart Multi-Agent Delivery", x, 10)
    draw_text(screen, small_font, "Strategy: " + STRATEGY_LABELS[sim.strategy], x, 32, MUTED)
    rows = [("Tick", str(sim.tick) + ("  (paused)" if paused else "  @ " + str(ticks_per_second) + "/s"), TEXT),
            ("Agents", "%d alive, %d failed" % (sim.alive_count(), sim.failed_count()), TEXT),
            ("Waiting tasks", str(m["waiting"]), TEXT),
            ("Completed", str(m["completed"]), GREEN),
            ("Avg delivery", avg, TEXT),
            ("Lost / recovered", "%d / %d" % (m["lost"], m["reassigned_tasks"]), RED if m["lost"] else TEXT),
            ("Avg reassign", reassign, TEXT),
            ("Dist / util", "%d cells, %.0f%%" % (m["total_distance"], 100 * m["utilization"]), TEXT),
            ("Messages", messages, TEXT),
            ("Dispatcher", dispatcher, dispatcher_colour)]
    y = 54
    for name, value, colour in rows:
        draw_text(screen, font, name, x, y, MUTED)
        draw_text(screen, font, value, x + 118, y, colour)
        y += 18
    y += 6
    draw_text(screen, font, "Agents", x, y, MUTED)
    y += 20
    for agent in sim.agents[:10]:
        pygame.draw.circle(screen, agent_colour(agent), (x + 6, y + 7), 6)
        draw_text(screen, small_font, "A" + str(agent.agent_id), x + 18, y, TEXT)
        pygame.draw.rect(screen, (30, 40, 55), (x + 48, y + 3, 60, 8))
        pygame.draw.rect(screen, GREEN if agent.battery > config.LOW_BATTERY else RED,
                         (x + 48, y + 3, int(60 * agent.battery / config.BATTERY_MAX), 8))
        draw_text(screen, small_font, agent.status.lower().replace("_", " "), x + 118, y,
                  RED if agent.status == FAILED else MUTED)
        y += 18
    y += 6
    for text, colour in [("Pickup (colour = priority)", PRIORITY_COLOURS[2]), ("Destination", DEST_BLUE),
                         ("Failed agent / orphaned task", RED)]:
        pygame.draw.rect(screen, colour, (x, y + 2, 10, 10))
        draw_text(screen, small_font, text, x + 18, y, MUTED)
        y += 16
    y += 4
    for text in ["SPACE pause  UP/DOWN speed  R new map", "TAB strategy  S split screen  D dispatcher",
                 "1 rush hour  2 failure storm  3 blocked road", "H heartbeats in feed  ESC quit",
                 "Click: fail vehicle  Right-click: block cell"]:
        draw_text(screen, small_font, text, x, y, MUTED)
        y += 14


def draw_stats(screen, sim, x, y, fonts, title):
    """Compact numbers under one grid in split-screen."""
    font, small_font = fonts[0], fonts[1]
    m, avg, reassign, dispatcher, dispatcher_colour, messages = metric_texts(sim)
    draw_text(screen, font, title, x, y, TEXT)
    rows = [("Agents", "%d alive, %d failed" % (sim.alive_count(), sim.failed_count()), TEXT),
            ("Completed", "%d  (waiting %d)" % (m["completed"], m["waiting"]), GREEN),
            ("Avg delivery", avg, TEXT),
            ("Lost / recovered", "%d / %d" % (m["lost"], m["reassigned_tasks"]), RED if m["lost"] else TEXT),
            ("Avg reassign", reassign, TEXT),
            ("Dispatcher" if sim.dispatcher is not None else "Messages",
             dispatcher if sim.dispatcher is not None else messages, dispatcher_colour if sim.dispatcher is not None else TEXT)]
    y += 18
    for name, value, colour in rows:
        draw_text(screen, small_font, name, x, y, MUTED)
        draw_text(screen, small_font, value, x + 130, y, colour)
        y += 16


def draw_feed(screen, sim, x, y, w, h, fonts, show_heartbeats):
    """The live message feed: what the agents are saying to each other right now."""
    small_font, tiny_font = fonts[1], fonts[3]
    pygame.draw.rect(screen, FEED_BG, (x, y, w, h))
    if sim.bus is None:
        draw_text(screen, small_font, "Live message feed: none. A central dispatcher decides, agents send no messages.", x + 10, y + 8, MUTED)
        return
    draw_text(screen, small_font, "Live message feed (Auction)" + ("" if show_heartbeats else "   heartbeats hidden, press H"),
              x + 10, y + 6, TEAL)
    lines = [e for e in sim.bus.log if show_heartbeats or e[1] != HEARTBEAT]
    lines = lines[-int((h - 26) / 15):]
    ly = y + 24
    for tick, msg_type, sender_id, payload in lines:
        draw_text(screen, tiny_font, "t=%-5d %s" % (tick, describe_message(msg_type, sender_id, payload)),
                  x + 10, ly, FEED_COLOURS.get(msg_type, MUTED))
        ly += 15


def draw_banner(screen, text, centre_x):
    if text:
        surface = pygame.font.Font(None, 26).render(text, True, BG)
        rect = surface.get_rect(center=(centre_x, 22))
        pygame.draw.rect(screen, YELLOW, rect.inflate(24, 10), border_radius=6)
        screen.blit(surface, rect)


# ---------- the two screen layouts ----------
def draw_single(screen, sim, fonts, ticks_per_second, paused, show_heartbeats, banner):
    screen.fill(BG)
    draw_world(screen, sim, View(0, 0, config.CELL_SIZE), fonts[1])
    draw_panel(screen, sim, fonts, ticks_per_second, paused)
    draw_feed(screen, sim, 0, config.GRID_HEIGHT * config.CELL_SIZE, SINGLE_SIZE[0], FEED_HEIGHT, fonts, show_heartbeats)
    draw_banner(screen, banner, config.GRID_WIDTH * config.CELL_SIZE // 2)


def split_views():
    return View(10, 40, SPLIT_CELL), View(630, 40, SPLIT_CELL)


def draw_split(screen, sims, fonts, ticks_per_second, paused, show_heartbeats, banner):
    screen.fill(BG)
    left, right = sims
    left_view, right_view = split_views()
    draw_text(screen, fonts[2], "%s   vs   Auction (decentralized)     tick %d  @ %d/s%s" %
              (STRATEGY_LABELS[left.strategy], left.tick, ticks_per_second, "  (paused)" if paused else ""), 10, 10)
    draw_world(screen, left, left_view, fonts[3])
    draw_world(screen, right, right_view, fonts[3])
    stats_y = left_view.oy + left_view.height() + 6
    draw_stats(screen, left, 10, stats_y, fonts, STRATEGY_LABELS[left.strategy])
    draw_stats(screen, right, 630, stats_y, fonts, STRATEGY_LABELS[right.strategy])
    draw_feed(screen, right, 0, 566, SPLIT_SIZE[0], SPLIT_SIZE[1] - 566, fonts, show_heartbeats)
    draw_banner(screen, banner, SPLIT_SIZE[0] // 2)


def main():
    max_frames = None
    if "--frames" in sys.argv:
        max_frames = int(sys.argv[sys.argv.index("--frames") + 1])
    split = "--split" in sys.argv

    pygame.init()
    pygame.display.set_caption("Smart Multi-Agent Delivery Simulator - Phase 11")
    clock = pygame.time.Clock()
    fonts = (pygame.font.Font(None, 20), pygame.font.Font(None, 17), pygame.font.Font(None, 24), pygame.font.Font(None, 15))

    seed = config.RANDOM_SEED
    single_strategy = config.STRATEGY
    left_strategy = "B2"

    def new_sims():
        if split:
            return [Simulation(seed, strategy=left_strategy), Simulation(seed, strategy="AUCTION")]
        return [Simulation(seed, strategy=single_strategy)]

    def new_screen():
        return pygame.display.set_mode(SPLIT_SIZE if split else SINGLE_SIZE)

    screen = new_screen()
    sims = new_sims()
    ticks_per_second = config.TICKS_PER_SECOND
    paused = False
    show_heartbeats = False
    banner, banner_until = "", 0
    accumulator = 0.0
    frames = 0
    running = True

    while running:
        dt = clock.tick(config.FPS) / 1000.0
        now = pygame.time.get_ticks()
        views = list(split_views()) if split else [View(0, 0, config.CELL_SIZE)]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                key = event.key
                if key == pygame.K_ESCAPE:
                    running = False
                elif key == pygame.K_SPACE:
                    paused = not paused
                elif key == pygame.K_UP:
                    ticks_per_second = min(60, ticks_per_second + 2)
                elif key == pygame.K_DOWN:
                    ticks_per_second = max(1, ticks_per_second - 2)
                elif key == pygame.K_h:
                    show_heartbeats = not show_heartbeats
                elif key == pygame.K_d:
                    if sims[0].dispatcher is not None:                  # only the central side has a dispatcher
                        sims[0].dispatcher.online = not sims[0].dispatcher.online
                elif key == pygame.K_r:
                    seed += 1
                    sims = new_sims()
                elif key == pygame.K_TAB:
                    if split:
                        left_strategy = "B1" if left_strategy == "B2" else "B2"
                    else:
                        single_strategy = STRATEGIES[(STRATEGIES.index(single_strategy) + 1) % len(STRATEGIES)]
                    sims = new_sims()
                elif key == pygame.K_s:
                    split = not split
                    screen = new_screen()
                    sims = new_sims()
                elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    if key == pygame.K_1:
                        banner = scenarios.rush_hour(sims)
                    elif key == pygame.K_2:
                        banner = scenarios.failure_storm(sims, rng=random.Random(seed * 13 + sims[0].tick))
                    else:
                        banner = scenarios.blocked_road(sims)
                    banner_until = now + 2500
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                for index, view in enumerate(views):
                    cell = view.pixel_to_cell(event.pos)
                    if cell is None:
                        continue
                    if event.button == 1:                               # fail the vehicle in ALL worlds
                        for agent in sims[index].agents:
                            if agent.is_alive() and agent.position == cell:
                                for sim in sims:
                                    sim.fail_agent(agent.agent_id)
                                break
                    else:                                               # block the cell in ALL worlds
                        blocked = sims[index].add_obstacle(cell)
                        if blocked is not None:
                            for other, sim in enumerate(sims):
                                if other != index:
                                    sim.add_obstacle(blocked)

        if not paused:
            accumulator += dt
            while accumulator >= 1.0 / ticks_per_second:
                for sim in sims:
                    sim.step()
                accumulator -= 1.0 / ticks_per_second

        text = banner if now < banner_until else ""
        if split:
            draw_split(screen, sims, fonts, ticks_per_second, paused, show_heartbeats, text)
        else:
            draw_single(screen, sims[0], fonts, ticks_per_second, paused, show_heartbeats, text)
        pygame.display.flip()

        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False

    pygame.quit()


if __name__ == "__main__":
    main()
