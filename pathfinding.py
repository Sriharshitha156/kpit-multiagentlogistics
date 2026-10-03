"""
pathfinding.py - A* shortest path on the grid.

A* explores cells in order of  f = g + h  where
   g = steps taken so far from the start
   h = a guess of the steps still needed (here: Manhattan distance to the goal)
Because Manhattan distance never over-estimates on a 4-direction grid, A* always
returns a SHORTEST path.
"""

import heapq

from environment import manhattan


def astar(start, goal, blocked, width, height):
    """
    Return the shortest path as a list of cells from just after `start` up to and
    including `goal`. Returns [] if start == goal, and None if no route exists.
    `blocked` is a set of cells that cannot be entered.
    """
    if start == goal:
        return []
    if goal in blocked:
        return None

    counter = 0                                   # tie-breaker so the heap never compares cells
    open_heap = [(manhattan(start, goal), counter, 0, start)]    # (f, counter, g, cell)
    came_from = {}                                # cell -> the cell we reached it from
    best_g = {start: 0}                           # cheapest known step count to each cell

    while open_heap:
        _, _, g, cell = heapq.heappop(open_heap)
        if cell == goal:
            path = []
            while cell != start:                  # walk backwards to rebuild the route
                path.append(cell)
                cell = came_from[cell]
            path.reverse()
            return path
        if g > best_g.get(cell, g):
            continue                              # an older, worse entry for this cell
        x, y = cell
        for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nx, ny = neighbour
            if not (0 <= nx < width and 0 <= ny < height) or neighbour in blocked:
                continue
            new_g = g + 1
            if new_g < best_g.get(neighbour, 10 ** 9):
                best_g[neighbour] = new_g
                came_from[neighbour] = cell
                counter += 1
                heapq.heappush(open_heap, (new_g + manhattan(neighbour, goal), counter, new_g, neighbour))
    return None
