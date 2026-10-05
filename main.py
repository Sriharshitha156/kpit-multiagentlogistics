"""
main.py - the Pygame window.   Run with:   python main.py          (add --split to start in split-screen,
                                                                     --nohelp to skip the welcome screen)

You do not steer anything: the vehicles run themselves. You create orders, break vehicles and
block roads, and watch how the fleet reacts. Press ? (or click Help) for a guide, and hover the
mouse over anything to see what it is.
"""

import csv
import os
import random
import sys

import pygame

import config
import scenarios
from agent import CHARGING, DELIVERING, FAILED, GOING_TO_CHARGE, GOING_TO_PICKUP
from communication import (COMMUNICATION_PARTITION, COMMUNICATION_RESTORED, HEARTBEAT, SYNC_COMPLETE,
                           SYNC_CONFLICT, describe_message, explain_message)
from metrics import summarize
from simulation import Simulation
from task import ASSIGNED, CANCELLED, COMPLETED, OPEN, PICKED_UP

# ---------- colours ----------
BG = (10, 26, 43)
GRID_LINE = (24, 48, 74)
OBSTACLE = (70, 82, 96)
CHARGER = (30, 150, 90)
PANEL_BG = (14, 34, 54)
FEED_BG = (7, 18, 30)
TOOLBAR_BG = (8, 20, 34)
BUTTON = (28, 58, 88)
BUTTON_HOVER = (44, 92, 132)
TEXT = (235, 240, 245)
MUTED = (150, 170, 190)
RED = (255, 92, 92)
YELLOW = (255, 210, 60)
GREEN = (60, 200, 120)
TEAL = (25, 195, 169)
DEST_BLUE = (90, 170, 255)
PRIORITY_COLOURS = {1: (130, 150, 175), 2: (255, 190, 60), 3: (255, 120, 70)}
PRIORITY_NAMES = {1: "low", 2: "medium", 3: "high"}
AGENT_COLOURS = [(25, 195, 169), (255, 140, 90), (120, 160, 255), (240, 120, 200),
                 (170, 220, 90), (255, 220, 100), (180, 130, 255), (100, 220, 230)]
FEED_COLOURS = {"TASK_REQUEST": TEXT, "TASK_BID": MUTED, "TASK_ACCEPT": TEAL, "TASK_CANCEL": RED,
                "DELIVERY_COMPLETE": GREEN,
                "TASK_REASSIGN": YELLOW, "AGENT_FAILURE": RED, "HEARTBEAT": (90, 110, 130),
                "VEHICLE_FAILED": RED, "ROAD_BLOCKED": YELLOW, "REROUTE_SUCCESS": GREEN,
                COMMUNICATION_PARTITION: RED, COMMUNICATION_RESTORED: TEAL,
                SYNC_COMPLETE: GREEN, SYNC_CONFLICT: YELLOW}

STRATEGIES = ["B1", "B2", "AUCTION"]
STRATEGY_LABELS = {"B1": "B1 central, nearest idle", "B2": "B2 central, same cost + battery rule",
                   "AUCTION": "Auction (decentralized)"}
STRATEGY_SHORT = {"B1": "B1", "B2": "B2", "AUCTION": "Auction"}

TOOLBAR_H = 40
FEED_HEIGHT = 120
SINGLE_SIZE = (config.GRID_WIDTH * config.CELL_SIZE + config.PANEL_WIDTH,
               TOOLBAR_H + config.GRID_HEIGHT * config.CELL_SIZE + FEED_HEIGHT)
SPLIT_CELL = 20
SPLIT_SIZE = (1240, 690)


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


def single_view():
    return View(0, TOOLBAR_H, config.CELL_SIZE)


def split_views():
    return View(10, 70, SPLIT_CELL), View(630, 70, SPLIT_CELL)


def agent_colour(agent):
    return AGENT_COLOURS[(agent.agent_id - 1) % len(AGENT_COLOURS)]


def draw_text(screen, font, text, x, y, colour=TEXT):
    screen.blit(font.render(text, True, colour), (x, y))


# ---------- drawing the world ----------
def draw_grid(screen, sim, view, label_font=None):
    c = view.cell
    for x in range(config.GRID_WIDTH + 1):
        pygame.draw.line(screen, GRID_LINE, (view.ox + x * c, view.oy), (view.ox + x * c, view.oy + view.height()))
    for y in range(config.GRID_HEIGHT + 1):
        pygame.draw.line(screen, GRID_LINE, (view.ox, view.oy + y * c), (view.ox + view.width(), view.oy + y * c))
    for (x, y) in sim.env.obstacles:
        pygame.draw.rect(screen, OBSTACLE, (view.ox + x * c + 1, view.oy + y * c + 1, c - 1, c - 1))
    for (x, y) in sim.env.chargers:
        rect = (view.ox + x * c + 3, view.oy + y * c + 3, c - 5, c - 5)
        pygame.draw.rect(screen, CHARGER, rect, border_radius=4)
        if label_font is not None and c >= 24:
            label = label_font.render("C", True, (230, 255, 240))
            screen.blit(label, label.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))


def draw_tasks(screen, sim, view, small_font):
    """Pickup = square (colour = priority) labelled P#. Drop-off = ring labelled D#. Red = orphaned."""
    failed_ids = {a.agent_id for a in sim.agents if a.status == FAILED}
    label_it = view.cell >= 24
    for task in sim.env.tasks:
        if task.status in (COMPLETED, CANCELLED):
            continue
        orphaned = task.owner_id in failed_ids
        dest = view.center(task.destination)
        if task.status in (OPEN, ASSIGNED):
            pickup = view.center(task.pickup)
            pygame.draw.line(screen, (45, 80, 115), pickup, dest, 1)
            half = max(3, view.cell // 4)
            colour = RED if orphaned else PRIORITY_COLOURS[task.priority]
            pygame.draw.rect(screen, colour, (pickup[0] - half, pickup[1] - half, half * 2, half * 2))
            if label_it:
                screen.blit(small_font.render("P%d" % task.task_id, True, colour), (pickup[0] + half + 1, pickup[1] - 14))
        pygame.draw.circle(screen, RED if orphaned else DEST_BLUE, dest, max(3, view.cell // 4), 2)
        screen.blit(small_font.render(("D%d" if label_it else "%d") % task.task_id, True, RED if orphaned else TEXT),
                    (dest[0] + 5, dest[1] - 13))


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
            pygame.draw.circle(screen, TEXT, (cx, cy), radius + 2, 2)
        label = small_font.render(str(agent.agent_id), True, (10, 20, 30))
        screen.blit(label, label.get_rect(center=(cx, cy)))
        bar_w = c - 6
        fill = int(bar_w * agent.battery / config.BATTERY_MAX)
        bar_colour = GREEN if agent.battery > 50 else (YELLOW if agent.battery > config.LOW_BATTERY else RED)
        pygame.draw.rect(screen, (30, 40, 55), (cx - bar_w // 2, cy - c // 2 - 1, bar_w, 4))
        pygame.draw.rect(screen, bar_colour, (cx - bar_w // 2, cy - c // 2 - 1, fill, 4))


def draw_world(screen, sim, view, small_font):
    draw_grid(screen, sim, view, small_font)
    draw_tasks(screen, sim, view, small_font)
    draw_routes(screen, sim, view)
    draw_agents(screen, sim, view, small_font)


# ---------- hover tooltips ----------
def tooltip_for(sim, cell):
    """Lines of text describing whatever is on `cell`, or None if the cell is empty."""
    here = [a for a in sim.agents if a.position == cell]
    if here:
        agent = sorted(here, key=lambda a: not a.is_alive())[0]
        if agent.status == FAILED:
            reason = "ran out of battery" if agent.fail_reason == "BATTERY" else "failed by you"
            return ["Vehicle A%d: FAILED" % agent.agent_id, "It " + reason + ".", "Its orders will be recovered by others."]
        holding = len(agent.task_queue) + (1 if agent.assigned_task is not None else 0)
        return ["Vehicle A%d: %s" % (agent.agent_id, agent.status.lower().replace("_", " ")),
                "Battery %d%%" % round(agent.battery), "Holding %d order(s), delivered %d" % (holding, agent.tasks_completed)]
    failed_ids = {a.agent_id for a in sim.agents if a.status == FAILED}
    for task in sim.env.tasks:
        if task.status in (COMPLETED, CANCELLED):
            continue
        at_pickup = cell == task.pickup and task.status in (OPEN, ASSIGNED)
        if not (at_pickup or cell == task.destination):
            continue
        if task.owner_id in failed_ids:
            state = "owner A%d failed: waiting for rescue" % task.owner_id
        elif task.status == OPEN:
            state = "waiting for a vehicle"
        elif task.status == ASSIGNED:
            state = "assigned to A%d" % task.owner_id
        else:
            state = "carried by A%d" % task.owner_id
        return ["Order #%d (%s priority)" % (task.task_id, PRIORITY_NAMES[task.priority]),
                "This is its %s." % ("pickup point" if at_pickup else "drop-off point"), state.capitalize(),
                "Deadline: tick %d" % task.deadline_tick]
    if cell in sim.env.chargers:
        return ["Charging station", "Vehicles recharge here."]
    if cell in sim.env.obstacles:
        return ["Blocked road", "Vehicles route around it."]
    return None


def draw_tooltip(screen, lines, mouse_pos, font):
    width = max(font.size(line)[0] for line in lines) + 16
    height = 8 + 17 * len(lines)
    x = min(mouse_pos[0] + 16, screen.get_width() - width - 4)
    y = min(mouse_pos[1] + 16, screen.get_height() - height - 4)
    pygame.draw.rect(screen, (4, 12, 20), (x, y, width, height), border_radius=6)
    pygame.draw.rect(screen, TEAL, (x, y, width, height), 1, border_radius=6)
    for i, line in enumerate(lines):
        draw_text(screen, font, line, x + 8, y + 5 + 17 * i, TEXT if i == 0 else MUTED)


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


def draw_panel(screen, sim, fonts, ticks_per_second, paused, top):
    """Right-hand panel of the single view: live metrics, agent list, short legend."""
    font, small_font, title_font = fonts[0], fonts[1], fonts[2]
    m, avg, reassign, dispatcher, dispatcher_colour, messages = metric_texts(sim)
    px = config.GRID_WIDTH * config.CELL_SIZE
    pygame.draw.rect(screen, PANEL_BG, (px, top, config.PANEL_WIDTH, config.GRID_HEIGHT * config.CELL_SIZE))
    x = px + 14
    draw_text(screen, title_font, "AutoSwarm | Urban EV delivery", x, top + 8)
    draw_text(screen, small_font, "Strategy: " + STRATEGY_LABELS[sim.strategy], x, top + 30, MUTED)
    if sim.bus is None:
        network = "not used"
    elif sim.bus.partitioned:
        network = "partitioned (%d groups)" % len(set(sim.bus.partition_group_by_agent.values()))
    elif sim.bus.network_restorations > sim.bus.synchronizations_completed:
        network = "synchronizing"
    else:
        network = "connected"
    rows = [("Tick", str(sim.tick) + ("  (paused)" if paused else "  @ " + str(ticks_per_second) + "/s"), TEXT),
            ("Agents", "%d alive, %d failed" % (sim.alive_count(), sim.failed_count()), TEXT),
            ("Waiting orders", str(m["waiting"]), TEXT),
            ("Completed", str(m["completed"]), GREEN),
            ("On time / late", "%d / %d" % (m["on_time"], m["late"]), GREEN if not m["late"] else RED),
            ("Overdue open", str(m["overdue_unfinished"]), RED if m["overdue_unfinished"] else TEXT),
            ("Avg delivery", avg, TEXT),
            ("Lost / recovered", "%d / %d" % (m["lost"], m["recovered_deliveries"]), RED if m["lost"] else TEXT),
            ("Affected / rate", "%d / %s" % (m["affected_orders"],
             "-" if m["recovery_rate"] is None else "%.0f%%" % (100 * m["recovery_rate"])), TEXT),
            ("Avg recovery", reassign, TEXT),
            ("Reroutes", "%d done / %d needed" % (m["successful_reroutes"], m["route_reroutes"]), TEXT),
            ("Distance / util.", "%d cells, %.0f%%" % (m["total_distance"], 100 * m["utilization"]), TEXT),
            ("Messages", messages, TEXT),
            ("Network", network, RED if "partitioned" in network else YELLOW if "synchronizing" in network else TEXT),
            ("Dispatcher", dispatcher, dispatcher_colour)]
    y = top + 50
    for name, value, colour in rows:
        draw_text(screen, font, name, x, y, MUTED)
        draw_text(screen, font, value, x + 155, y, colour)
        y += 17
    y += 4
    draw_text(screen, font, "Vehicles (battery, action)", x, y, MUTED)
    y += 19
    for agent in sim.agents[:10]:
        pygame.draw.circle(screen, agent_colour(agent), (x + 6, y + 7), 6)
        draw_text(screen, small_font, "A" + str(agent.agent_id), x + 18, y, TEXT)
        pygame.draw.rect(screen, (30, 40, 55), (x + 48, y + 3, 60, 8))
        pygame.draw.rect(screen, GREEN if agent.battery > config.LOW_BATTERY else RED,
                         (x + 48, y + 3, int(60 * agent.battery / config.BATTERY_MAX), 8))
        draw_text(screen, small_font, agent.status.lower().replace("_", " "), x + 118, y,
                  RED if agent.status == FAILED else MUTED)
        y += 16
    y += 6
    for text in ["Square: pickup (P#). Ring: drop-off (D#)", "Red: failed vehicle / orphaned order",
                 "White ring: carrying. Yellow: charging"]:
        draw_text(screen, small_font, text, x, y, MUTED)
        y += 14
    draw_text(screen, small_font, "Hover for details. Click Help for a guide.", x, y + 2, TEAL)


def draw_stats(screen, sim, x, y, fonts, title):
    """Compact numbers under one grid in split-screen."""
    font, small_font = fonts[0], fonts[1]
    m, avg, reassign, dispatcher, dispatcher_colour, messages = metric_texts(sim)
    draw_text(screen, font, title, x, y, TEXT)
    central = sim.dispatcher is not None
    rows = [("Agents", "%d alive, %d failed" % (sim.alive_count(), sim.failed_count()), TEXT),
            ("Completed", "%d  (waiting %d)" % (m["completed"], m["waiting"]), GREEN),
            ("On time / late", "%d / %d" % (m["on_time"], m["late"]), GREEN if not m["late"] else RED),
            ("Avg delivery", avg, TEXT),
            ("Lost / recovered", "%d / %d" % (m["lost"], m["reassigned_tasks"]), RED if m["lost"] else TEXT),
            ("Avg reassign", reassign, TEXT),
            ("Rescue", "%d cells / %d done" % (m["recovery_approach_distance"], m["recovered_deliveries"]), TEXT),
            ("Dispatcher" if central else "Messages", dispatcher if central else messages,
             dispatcher_colour if central else TEXT)]
    y += 18
    for name, value, colour in rows:
        draw_text(screen, small_font, name, x, y, MUTED)
        draw_text(screen, small_font, value, x + 130, y, colour)
        y += 14


def draw_feed(screen, sim, x, y, w, h, fonts, show_heartbeats, technical=False):
    """The live message feed: what the vehicles are saying to each other right now."""
    small_font, tiny_font = fonts[1], fonts[3]
    pygame.draw.rect(screen, FEED_BG, (x, y, w, h))
    if sim.bus is None:
        draw_text(screen, small_font, "Live message feed: none. A central dispatcher decides, vehicles send no messages.",
                  x + 10, y + 8, MUTED)
        return
    title = "Technical message log (T to explain)" if technical else "What is happening (T for technical log)"
    draw_text(screen, small_font, title + ("" if show_heartbeats else "   heartbeats hidden: press H"),
              x + 10, y + 6, TEAL)
    lines = [e for e in sim.bus.log if show_heartbeats or e[1] != HEARTBEAT]
    lines = lines[-max(1, int((h - 26) / 15)):]
    ly = y + 24
    for tick, msg_type, sender_id, payload in lines:
        description = (describe_message(msg_type, sender_id, payload) if technical
                       else explain_message(msg_type, sender_id, payload))
        draw_text(screen, tiny_font, "t=%-5d %s" % (tick, description),
                  x + 10, ly, FEED_COLOURS.get(msg_type, MUTED))
        ly += 15


def draw_auction_overlay(screen, sim, record, record_index, record_count, fonts):
    """Show a read-only explanation of one auction reconstructed from bus sends."""
    width, height = screen.get_size()
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((5, 12, 22, 225))
    screen.blit(overlay, (0, 0))
    font, small_font, title_font = fonts[0], fonts[1], fonts[2]
    panel_w, panel_h = min(820, width - 48), min(500, height - 48)
    panel = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
    pygame.draw.rect(screen, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(screen, TEAL, panel, 2, border_radius=10)
    x, y = panel.x + 22, panel.y + 18

    if record is None:
        draw_text(screen, title_font, "Auction details", x, y, TEAL)
        draw_text(screen, font, "No auction messages have been recorded yet.", x, y + 42)
    else:
        task_id, epoch = record["task_id"], record["epoch"]
        priority = record["priority"]
        priority_label = {1: "low", 2: "medium", 3: "high"}.get(priority, "unknown")
        draw_text(screen, title_font,
                  "Task #%d  |  %s priority  |  auction %d" % (task_id, priority_label, epoch), x, y, TEAL)
        y += 38
        draw_text(screen, font, "Agents that submitted feasible bids (lower cost wins):", x, y)
        y += 27
        bids = sorted(record["bids"].items(), key=lambda item: (item[1], item[0]))
        if bids:
            for agent_id, cost in bids:
                details = record.get("bid_details", {}).get(agent_id, {})
                battery = "battery %.0f%%" % details.get("battery_pct", 0) if details else ""
                draw_text(screen, small_font, "A%d   score %.3f   %s" % (agent_id, cost, battery), x + 12, y, TEXT)
                y += 21
        else:
            draw_text(screen, small_font, "No bids recorded for this auction.", x + 12, y, MUTED)
            y += 21

        bidder_ids = set(record["bids"])
        no_bid_ids = [agent.agent_id for agent in sim.agents if agent.agent_id not in bidder_ids]
        if no_bid_ids:
            names = ", ".join("A%d" % agent_id for agent_id in no_bid_ids)
            draw_text(screen, small_font, "No bid recorded: " + names, x + 12, y, MUTED)
            y += 21
            draw_text(screen, small_font, "This can mean infeasible or no bid message recorded.", x + 12, y, MUTED)
            y += 25

        accepts = sorted(record["accepts"].items(), key=lambda item: (item[1], item[0]))
        if len(accepts) == 1:
            winner_id, winner_cost = accepts[0]
            draw_text(screen, font, "Winner: A%d (accepted at %.3f)" % (winner_id, winner_cost), x, y, GREEN)
            y += 24
            expected = min(bids, key=lambda item: (item[1], item[0])) if bids else None
            details = record.get("bid_details", {}).get(winner_id, {})
            if details:
                draw_text(screen, small_font,
                          "Score = time weight × (priority × pickup ETA + delivery time) + load weight × current load",
                          x, y, MUTED)
                y += 19
                draw_text(screen, small_font,
                          "Winner A%d: pickup %d cells / %.1f ticks; delivery %d cells / %.1f ticks; load %d; priority ×%.2f" %
                          (winner_id, details["distance_to_pickup"], details["pickup_time"],
                           details["delivery_distance"], details["delivery_time"], details["load"],
                           details["priority_factor"]), x, y, TEXT)
                y += 19
                draw_text(screen, small_font,
                          "Battery %.1f%%; energy need incl. reserve %.1f units (battery is an eligibility check)" %
                          (details["battery_pct"], details["energy_required_with_reserve"]), x, y, MUTED)
                y += 22
            if expected == (winner_id, winner_cost):
                draw_text(screen, small_font, "Reason: lowest recorded bid; ties go to the lower agent ID.", x, y)
            else:
                draw_text(screen, small_font, "Accept differs from recorded bids; agents may have received different messages.", x, y, YELLOW)
        elif accepts:
            claims = ", ".join("A%d (%.3f)" % claim for claim in accepts)
            draw_text(screen, font, "Conflicting accept claims: " + claims, x, y, YELLOW)
            y += 24
            draw_text(screen, small_font, "This auction did not produce one consistent winner claim.", x, y, YELLOW)
        elif bids:
            draw_text(screen, font, "Winner: pending acceptance", x, y, YELLOW)
        else:
            draw_text(screen, font, "Winner: none recorded", x, y, MUTED)

    footer = "Auction %d of %d   |   Left/Right: browse   |   A, Esc, or click: close" % (
        record_index + 1 if record_count else 0, record_count)
    draw_text(screen, small_font, footer, panel.x + 22, panel.bottom - 30, MUTED)


def draw_banner(screen, text, centre_x, y):
    if text:
        surface = pygame.font.Font(None, 26).render(text, True, BG)
        rect = surface.get_rect(center=(centre_x, y))
        pygame.draw.rect(screen, YELLOW, rect.inflate(24, 10), border_radius=6)
        screen.blit(surface, rect)


RESULT_TABS = [("Deadlines", "paired-deadlines", "deadline_scenarios"),
               ("Scale", "paired-scale-clean", "scale_agents"),
               ("Recovery", "paired-deadlines", "deadline_scenarios"),
               ("Network", "paired-partition", "communication_partition")]


def load_result_rows(suite, experiment):
    """Read locally generated summary data; never invent a fallback result."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", suite, "summary.csv")
    if not os.path.isfile(path):
        return path, []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return path, [row for row in csv.DictReader(handle) if row.get("experiment") == experiment]


def draw_analytics_overlay(screen, tab_index, fonts):
    width, height = screen.get_size()
    veil = pygame.Surface((width, height), pygame.SRCALPHA)
    veil.fill((5, 12, 22, 238))
    screen.blit(veil, (0, 0))
    panel = pygame.Rect(36, 32, width - 72, height - 64)
    pygame.draw.rect(screen, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(screen, TEAL, panel, 2, border_radius=10)
    font, small, title = fonts[0], fonts[1], fonts[2]
    draw_text(screen, title, "AutoSwarm | Experiment results", panel.x + 22, panel.y + 16, TEAL)
    y = panel.y + 52
    for i, (name, _, _) in enumerate(RESULT_TABS):
        draw_text(screen, small, ("[ %s ]" if i == tab_index else "  %s  ") % name,
                  panel.x + 22 + i * 150, y, YELLOW if i == tab_index else MUTED)
    name, suite, experiment = RESULT_TABS[tab_index]
    path, rows = load_result_rows(suite, experiment)
    y += 36
    draw_text(screen, small, "Source: results/%s/summary.csv  |  x axis: %s  |  mean ± std across seeds" %
              (suite, "network condition" if name == "Network" else "scenario / fleet size"), panel.x + 22, y, MUTED)
    y += 25
    if not rows:
        draw_text(screen, font, "No saved results for this tab yet.", panel.x + 22, y, YELLOW)
        draw_text(screen, small, "Run: python experiments/run_experiments.py --suite %s" % suite,
                  panel.x + 22, y + 27, TEXT)
    else:
        metric_names = ({"Deadlines": ["on_time_rate", "late", "overdue_unfinished", "completed"],
                         "Scale": ["completion_rate", "completed", "compute_seconds", "msgs_per_completed"],
                         "Recovery": ["on_time_rate", "late", "lost", "avg_reassign_time"],
                         "Network": ["completion_rate", "partitioned_messages", "sync_conflicts",
                                     "synchronizations_completed"]})[name]
        metric_labels = {"on_time_rate": "On-time %", "late": "Late orders",
                         "overdue_unfinished": "Overdue open", "completed": "Delivered",
                         "completion_rate": "Completion %", "compute_seconds": "Runtime (s)",
                         "msgs_per_completed": "Msgs / delivery", "lost": "Lost orders",
                         "avg_reassign_time": "Recovery ticks", "partitioned_messages": "Blocked msgs",
                         "sync_conflicts": "Conflicts", "synchronizations_completed": "Syncs"}
        headers = ["Scenario", "Fleet", "Seeds"] + [metric_labels.get(metric, metric) for metric in metric_names]
        positions = [panel.x + 22, panel.x + 175, panel.x + 275]
        positions += [panel.x + 350 + i * max(110, (panel.width - 380) // len(metric_names))
                      for i in range(len(metric_names))]
        for idx, header in enumerate(headers):
            draw_text(screen, small, header, positions[idx], y, TEAL)
        y += 23
        for row in rows[:max(1, int((panel.bottom - y - 32) / 22))]:
            values = [row.get("x", ""), row.get("strategy", ""), row.get("n", "")]
            for metric in metric_names:
                mean, std = row.get(metric + "_mean", ""), row.get(metric + "_std", "")
                if mean:
                    try:
                        mean_value = float(mean)
                        fmt = "%.1f%%" % (100 * mean_value) if metric in ("on_time_rate", "completion_rate") else "%.2f" % mean_value
                        std_value = float(std) if std else 0
                        if metric in ("on_time_rate", "completion_rate"):
                            std_value *= 100
                        fmt += " ± %.2f" % std_value if std else ""
                    except ValueError:
                        fmt = mean
                else:
                    fmt = "—"
                values.append(fmt)
            for idx, value in enumerate(values):
                draw_text(screen, small, str(value), positions[idx], y, TEXT)
            y += 22
    draw_text(screen, small, "Left/Right: switch results  |  E or Esc: close  |  values come from saved CSVs",
              panel.x + 22, panel.bottom - 28, MUTED)


# ---------- toolbar ----------
def layout_buttons(groups, font, total_width, y=7, height=26):
    """
    Place the toolbar buttons left to right. `groups` is a list of lists of dictionaries with a
    'label'. Returns a list of (pygame.Rect, button). Padding shrinks if the window is narrow.
    """
    for padding in (12, 9, 6, 4):
        x, placed = 8, []
        for group in groups:
            for button in group:
                width = font.size(button["label"])[0] + 2 * padding
                placed.append((pygame.Rect(x, y, width, height), button))
                x += width + 5
            x += 9
        if x - 14 <= total_width:
            break
    return placed


def draw_toolbar(screen, placed, font, mouse_pos, width):
    pygame.draw.rect(screen, TOOLBAR_BG, (0, 0, width, TOOLBAR_H))
    for rect, button in placed:
        if not button["enabled"]:
            colour, text_colour = (22, 38, 56), (95, 110, 128)
        elif rect.collidepoint(mouse_pos):
            colour, text_colour = BUTTON_HOVER, TEXT
        else:
            colour, text_colour = BUTTON, TEAL if button.get("active") else TEXT
        pygame.draw.rect(screen, colour, rect, border_radius=6)
        label = font.render(button["label"], True, text_colour)
        screen.blit(label, label.get_rect(center=rect.center))


# ---------- the help overlay ----------
def draw_help(screen, fonts):
    width, height = screen.get_size()
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((5, 12, 22, 242))
    screen.blit(overlay, (0, 0))
    font, small_font, title_font = fonts[0], fonts[1], fonts[2]
    big = pygame.font.Font(None, 34)
    draw_text(screen, big, "How to read and use this simulator", 50, 26)
    draw_text(screen, font, "You do not steer anything. The vehicles run themselves. You create orders, break vehicles and block roads,",
              50, 66, TEXT)
    draw_text(screen, font, "and watch how the fleet reacts. There is no central boss: vehicles bid for orders and rescue each other's work.",
              50, 86, TEXT)

    draw_text(screen, title_font, "What you see", 50, 122, TEAL)
    y = 152
    icons = [("vehicle", "Delivery vehicle. The bar above it is its battery."),
             ("carry", "White ring: it is carrying a parcel."),
             ("charge", "Yellow ring: it is charging at a station."),
             ("failed", "Grey circle with X: a failed vehicle."),
             ("pickup", "Square P#: pickup point (colour = priority)."),
             ("dropoff", "Ring D#: drop-off point of that order."),
             ("orphan", "Red order: its vehicle failed, waiting for rescue."),
             ("charger", "Green square C: charging station."),
             ("block", "Grey block: a blocked road."),
             ("route", "Coloured line: the route a vehicle planned (A*).")]
    for kind, text in icons:
        cx, cy = 62, y + 9
        if kind == "vehicle":
            pygame.draw.circle(screen, AGENT_COLOURS[0], (cx, cy), 8)
        elif kind == "carry":
            pygame.draw.circle(screen, AGENT_COLOURS[1], (cx, cy), 7)
            pygame.draw.circle(screen, TEXT, (cx, cy), 9, 2)
        elif kind == "charge":
            pygame.draw.circle(screen, AGENT_COLOURS[2], (cx, cy), 7)
            pygame.draw.circle(screen, YELLOW, (cx, cy), 9, 2)
        elif kind == "failed":
            pygame.draw.circle(screen, (90, 90, 100), (cx, cy), 8)
            pygame.draw.line(screen, RED, (cx - 5, cy - 5), (cx + 5, cy + 5), 3)
            pygame.draw.line(screen, RED, (cx - 5, cy + 5), (cx + 5, cy - 5), 3)
        elif kind == "pickup":
            pygame.draw.rect(screen, PRIORITY_COLOURS[2], (cx - 6, cy - 6, 12, 12))
        elif kind == "dropoff":
            pygame.draw.circle(screen, DEST_BLUE, (cx, cy), 7, 2)
        elif kind == "orphan":
            pygame.draw.rect(screen, RED, (cx - 6, cy - 6, 12, 12))
        elif kind == "charger":
            pygame.draw.rect(screen, CHARGER, (cx - 8, cy - 8, 16, 16), border_radius=4)
        elif kind == "block":
            pygame.draw.rect(screen, OBSTACLE, (cx - 8, cy - 8, 16, 16))
        else:
            pygame.draw.line(screen, AGENT_COLOURS[0], (cx - 9, cy + 3), (cx + 9, cy - 3), 2)
        draw_text(screen, font, text, 86, y, TEXT)
        y += 25

    draw_text(screen, title_font, "What you can do (toolbar buttons or keys)", 600, 122, TEAL)
    y = 152
    for text in ["Pause / Slower / Faster:  SPACE, DOWN, UP", "Rush hour (1): 12 new orders arrive at once",
                 "Fail 3 (2): three vehicles break down together", "Block roads (3): 12 roads become blocked",
                 "Recovery demo (4): deterministic failure while carrying a task",
                 "Left-click a vehicle: fail that vehicle", "Right-click a cell: block that road",
                 "Hover over anything: see what it is", "Split screen (S): central dispatcher vs our fleet",
                 "Dispatcher (D): switch the central dispatcher off", "Heartbeats (H): show heartbeat messages in the feed",
                 "Cancel waiting order (C): withdraw the oldest unassigned order",
                 "Auction bids (A): inspect bids, accepted winner, and prior auctions",
                 "New map (R), Strategy (TAB), Help (?), Quit (ESC)"]:
        draw_text(screen, font, text, 600, y, TEXT)
        y += 25

    draw_text(screen, title_font, "Try this in 60 seconds", 50, 432, TEAL)
    y = 462
    for text in ["1. Click Rush hour. Watch the feed at the bottom: orders are announced, vehicles bid, one wins.",
                 "2. Left-click a vehicle that has a coloured line. It fails and its order turns red.",
                 "3. About 15 ticks later another vehicle takes the order over. The panel shows Lost / recovered 0 / 1.",
                 "4. Click Split screen, then Dispatcher, then Rush hour: the central side stops, our fleet keeps working."]:
        draw_text(screen, font, text, 50, y, TEXT)
        y += 24
    draw_text(screen, title_font, "Click anywhere or press any key to close. Click Help (or press ?) to open this again.",
              50, height - 40, YELLOW)


# ---------- the application ----------
class App:
    """Holds the state of the window: the simulation(s), the speed and the buttons."""

    def __init__(self, split=False, show_help=True, transport="inprocess"):
        pygame.init()
        caption = "AutoSwarm - Urban EV Delivery Simulator"
        if transport == "udp":
            caption += " - localhost UDP"
        pygame.display.set_caption(caption)
        self.fonts = (pygame.font.Font(None, 20), pygame.font.Font(None, 17), pygame.font.Font(None, 24),
                      pygame.font.Font(None, 15))
        self.button_font = pygame.font.Font(None, 18)
        self.split = split
        self.transport = transport
        self.seed = config.RANDOM_SEED
        self.single_strategy = config.STRATEGY
        self.left_strategy = "B2"
        self.ticks_per_second = config.TICKS_PER_SECOND
        self.paused = False
        self.show_heartbeats = False
        self.show_technical_feed = False
        self.help_open = show_help
        self.auction_open = False
        self.analytics_open = False
        self.analytics_tab = 0
        self.auction_index = 0
        self.banner, self.banner_until = "", 0
        self.accumulator = 0.0
        self.running = True
        self.screen = self._new_screen()
        self.sims = self._new_sims()

    # ----- setup -----
    def _new_screen(self):
        return pygame.display.set_mode(SPLIT_SIZE if self.split else SINGLE_SIZE)

    def _new_sims(self):
        for sim in getattr(self, "sims", []):
            sim.close()
        if self.split:
            return [Simulation(self.seed, strategy=self.left_strategy, transport=self.transport),
                    Simulation(self.seed, strategy="AUCTION", transport=self.transport)]
        return [Simulation(self.seed, strategy=self.single_strategy, transport=self.transport)]

    def views(self):
        return list(split_views()) if self.split else [single_view()]

    def cancellable_task_ids(self):
        """Tasks still open in every displayed world, so split comparisons stay paired."""
        open_ids = [{task.task_id for task in sim.env.tasks if task.status == OPEN} for sim in self.sims]
        return set.intersection(*open_ids) if open_ids else set()

    def say(self, text, seconds=2.5):
        self.banner, self.banner_until = text, pygame.time.get_ticks() + int(seconds * 1000)

    # ----- the toolbar -----
    def button_groups(self):
        central = self.sims[0].dispatcher
        if central is None:
            dispatcher_label, dispatcher_enabled = "Dispatch: --", False
        else:
            dispatcher_label, dispatcher_enabled = "Dispatch " + ("ON" if central.online else "OFF"), True
        strategy = self.left_strategy if self.split else self.single_strategy
        auction_sim = self._auction_sim()
        network_available = bool(auction_sim and len([a for a in auction_sim.agents if a.is_alive()]) >= 2)
        network_label = "Restore" if auction_sim and auction_sim.bus and auction_sim.bus.partitioned else "Partition"
        return [[{"action": "help", "label": "Help", "enabled": True},
                 {"action": "auction", "label": "Bids (A)", "enabled": True},
                 {"action": "analytics", "label": "Results", "enabled": True}],
                [{"action": "pause", "label": "Resume" if self.paused else "Pause", "enabled": True, "active": self.paused},
                 {"action": "slower", "label": "-Speed", "enabled": True},
                 {"action": "faster", "label": "+Speed", "enabled": True}],
                [{"action": "rush", "label": "Rush", "enabled": True},
                 {"action": "storm", "label": "Fail 3", "enabled": True},
                 {"action": "block", "label": "Block", "enabled": True}],
                [{"action": "new_map", "label": "Map", "enabled": True},
                 {"action": "strategy", "label": "Mode " + STRATEGY_SHORT[strategy], "enabled": True},
                 {"action": "split", "label": "Split", "enabled": True, "active": self.split}],
                [{"action": "dispatcher", "label": dispatcher_label, "enabled": dispatcher_enabled},
                 {"action": "network", "label": network_label, "enabled": network_available},
                 {"action": "heartbeats", "label": "HB" + ("+" if self.show_heartbeats else "-"),
                  "enabled": True},
                 {"action": "cancel", "label": "Cancel",
                  "enabled": bool(self.cancellable_task_ids())}]]

    def button_rects(self):
        return layout_buttons(self.button_groups(), self.button_font, self.screen.get_width())

    # ----- actions (used by both keys and buttons) -----
    def act(self, name):
        if name == "help":
            self.help_open = not self.help_open
        elif name == "auction":
            self.auction_open = not self.auction_open
            if self.auction_open:
                sim = self._auction_sim()
                self.auction_index = max(0, len(sim.bus.auction_history) - 1) if sim and sim.bus else 0
        elif name == "analytics":
            self.analytics_open = not self.analytics_open
        elif name == "technical_feed":
            self.show_technical_feed = not self.show_technical_feed
        elif name == "network":
            sim = self._auction_sim()
            if sim is None or sim.bus is None:
                self.say("Network partition is available for the auction fleet")
            elif sim.bus.partitioned:
                sim.restore_network()
                self.say("Network restored; vehicles are exchanging task ledgers", seconds=3)
            else:
                agents = [agent.agent_id for agent in sim.agents if agent.is_alive()]
                midpoint = max(1, len(agents) // 2)
                groups = [agents[:midpoint], agents[midpoint:]]
                sim.partition_network(groups)
                self.say("Communication split into 2 local groups. Press 1 to add an order.", seconds=4)
        elif name == "cancel":
            task_ids = self.cancellable_task_ids()
            if not task_ids:
                self.say("No waiting order to cancel")
            else:
                task_id = min(task_ids, key=lambda candidate_id: (
                    self.sims[0].env.task_by_id[candidate_id].created_tick, candidate_id))
                cancelled = sum(sim.cancel_task(task_id) for sim in self.sims)
                self.say("Cancelled waiting order #%d (%d view%s)" %
                         (task_id, cancelled, "" if cancelled == 1 else "s"))
        elif name == "recovery_demo":
            self.sims = self._new_sims()
            self.auction_open = False
            self.say(scenarios.failure_recovery_demo(self.sims), seconds=4)
        elif name == "pause":
            self.paused = not self.paused
        elif name == "faster":
            self.ticks_per_second = min(60, self.ticks_per_second + 2)
        elif name == "slower":
            self.ticks_per_second = max(1, self.ticks_per_second - 2)
        elif name == "rush":
            self.say(scenarios.rush_hour(self.sims))
        elif name == "storm":
            self.say(scenarios.failure_storm(self.sims, rng=random.Random(self.seed * 13 + self.sims[0].tick)))
        elif name == "block":
            self.say(scenarios.blocked_road(self.sims))
        elif name == "new_map":
            self.seed += 1
            self.sims = self._new_sims()
            self.say("New map")
        elif name == "strategy":
            if self.split:
                self.left_strategy = "B1" if self.left_strategy == "B2" else "B2"
            else:
                self.single_strategy = STRATEGIES[(STRATEGIES.index(self.single_strategy) + 1) % len(STRATEGIES)]
            self.sims = self._new_sims()
            self.say("Strategy: " + STRATEGY_LABELS[self.left_strategy if self.split else self.single_strategy])
        elif name == "split":
            self.split = not self.split
            self.screen = self._new_screen()
            self.sims = self._new_sims()
            self.say("Split screen: central dispatcher (left) vs our fleet (right)" if self.split else "Single view")
        elif name == "dispatcher":
            dispatcher = self.sims[0].dispatcher
            if dispatcher is not None:
                dispatcher.online = not dispatcher.online
                self.say("Dispatcher " + ("back ONLINE" if dispatcher.online else "switched OFF"))
        elif name == "heartbeats":
            self.show_heartbeats = not self.show_heartbeats
        elif name == "quit":
            self.running = False

    KEYS = {pygame.K_SPACE: "pause", pygame.K_UP: "faster", pygame.K_DOWN: "slower", pygame.K_1: "rush",
            pygame.K_2: "storm", pygame.K_3: "block", pygame.K_4: "recovery_demo", pygame.K_r: "new_map", pygame.K_TAB: "strategy",
            pygame.K_s: "split", pygame.K_d: "dispatcher", pygame.K_h: "heartbeats", pygame.K_a: "auction", pygame.K_F1: "help",
            pygame.K_c: "cancel", pygame.K_e: "analytics", pygame.K_p: "network", pygame.K_t: "technical_feed",
            pygame.K_QUESTION: "help", pygame.K_SLASH: "help"}

    def _auction_sim(self):
        """Return the auction run to inspect (the right side in split-screen)."""
        return next((sim for sim in reversed(self.sims) if sim.bus is not None), None)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if self.help_open and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.help_open = False                       # any key or click closes the guide
            return
        if self.auction_open:
            if event.type == pygame.KEYDOWN:
                sim = self._auction_sim()
                count = len(sim.bus.auction_history) if sim and sim.bus else 0
                if event.key == pygame.K_LEFT and count:
                    self.auction_index = max(0, self.auction_index - 1)
                elif event.key == pygame.K_RIGHT and count:
                    self.auction_index = min(count - 1, self.auction_index + 1)
                else:
                    self.auction_open = False
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.auction_open = False
                return
        if self.analytics_open:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.analytics_tab = (self.analytics_tab - 1) % len(RESULT_TABS)
                elif event.key == pygame.K_RIGHT:
                    self.analytics_tab = (self.analytics_tab + 1) % len(RESULT_TABS)
                else:
                    self.analytics_open = False
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.analytics_open = False
                return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.act("quit")
            elif getattr(event, "unicode", "") == "?" or event.key in self.KEYS:
                self.act("help" if getattr(event, "unicode", "") == "?" else self.KEYS[event.key])
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            if event.button == 1:
                for rect, button in self.button_rects():
                    if rect.collidepoint(event.pos):
                        if button["enabled"]:
                            self.act(button["action"])
                        return
            for index, view in enumerate(self.views()):
                cell = view.pixel_to_cell(event.pos)
                if cell is None:
                    continue
                if event.button == 1:                    # fail the vehicle in ALL worlds
                    for agent in self.sims[index].agents:
                        if agent.is_alive() and agent.position == cell:
                            for sim in self.sims:
                                sim.fail_agent(agent.agent_id)
                            self.say("Vehicle A%d failed" % agent.agent_id)
                            break
                else:                                    # block the cell in ALL worlds
                    blocked = self.sims[index].add_obstacle(cell)
                    if blocked is None:
                        self.say("That cell cannot be blocked (vehicle, order, charger, or it would cut the map)")
                    else:
                        for other, sim in enumerate(self.sims):
                            if other != index:
                                sim.add_obstacle(blocked)

    def update(self, dt):
        if self.paused or self.help_open:
            return
        self.accumulator += dt
        while self.accumulator >= 1.0 / self.ticks_per_second:
            for sim in self.sims:
                sim.step()
            self.accumulator -= 1.0 / self.ticks_per_second

    # ----- drawing -----
    def draw(self):
        screen, fonts = self.screen, self.fonts
        mouse = pygame.mouse.get_pos()
        banner = self.banner if pygame.time.get_ticks() < self.banner_until else ""
        screen.fill(BG)
        if self.split:
            left, right = self.sims
            left_view, right_view = split_views()
            draw_text(screen, fonts[2], "%s   vs   Auction (decentralized)     tick %d  @ %d/s%s" %
                      (STRATEGY_LABELS[left.strategy], left.tick, self.ticks_per_second, "  (paused)" if self.paused else ""),
                      10, 46)
            draw_world(screen, left, left_view, fonts[3])
            draw_world(screen, right, right_view, fonts[3])
            stats_y = left_view.oy + left_view.height() + 6
            draw_stats(screen, left, 10, stats_y, fonts, STRATEGY_LABELS[left.strategy])
            draw_stats(screen, right, 630, stats_y, fonts, STRATEGY_LABELS[right.strategy])
            draw_feed(screen, right, 0, 596, SPLIT_SIZE[0], SPLIT_SIZE[1] - 596, fonts,
                      self.show_heartbeats, self.show_technical_feed)
            banner_x = SPLIT_SIZE[0] // 2
        else:
            sim, view = self.sims[0], single_view()
            draw_world(screen, sim, view, fonts[1])
            draw_panel(screen, sim, fonts, self.ticks_per_second, self.paused, TOOLBAR_H)
            draw_feed(screen, sim, 0, TOOLBAR_H + view.height(), SINGLE_SIZE[0], FEED_HEIGHT, fonts,
                      self.show_heartbeats, self.show_technical_feed)
            banner_x = view.width() // 2
        draw_toolbar(screen, self.button_rects(), self.button_font, mouse, screen.get_width())
        draw_banner(screen, banner, banner_x, TOOLBAR_H + (60 if self.split else 24))
        if not self.help_open:
            for index, view in enumerate(self.views()):
                cell = view.pixel_to_cell(mouse)
                lines = tooltip_for(self.sims[index], cell) if cell is not None else None
                if lines:
                    draw_tooltip(screen, lines, mouse, fonts[1])
        if self.help_open:
            draw_help(screen, fonts)
        elif self.auction_open:
            sim = self._auction_sim()
            history = sim.bus.auction_history if sim and sim.bus else []
            if history:
                self.auction_index = min(self.auction_index, len(history) - 1)
                record = history[self.auction_index]
            else:
                record = None
            draw_auction_overlay(screen, sim, record, self.auction_index, len(history), fonts)
        elif self.analytics_open:
            draw_analytics_overlay(screen, self.analytics_tab, fonts)
        pygame.display.flip()

    def run(self, max_frames=None):
        clock = pygame.time.Clock()
        frames = 0
        while self.running:
            dt = clock.tick(config.FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        for sim in self.sims:
            sim.close()
        pygame.quit()


def main():
    max_frames = int(sys.argv[sys.argv.index("--frames") + 1]) if "--frames" in sys.argv else None
    transport = "udp" if "--udp" in sys.argv else "inprocess"
    App(split="--split" in sys.argv, show_help="--nohelp" not in sys.argv,
        transport=transport).run(max_frames)


if __name__ == "__main__":
    main()
