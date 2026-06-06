# ─── ai_system.py  v5.1 ──────────────────────────────────────────
"""
A* pathfinding + Line-of-sight  —  Final Production Version

astar(game_map, start, goal)
    (col,row) path list from start to goal. Excludes start tile.
    Empty list if unreachable or start==goal.
    4-directional movement. Manhattan heuristic.
    Auto-clamps goal to nearest walkable tile if goal is a wall.
    Bounds-checks all neighbours.

has_los(game_map, ax, ay, bx, by)
    Pixel-space line-of-sight. Samples every (TILE_SIZE//3) pixels.
    Out-of-bounds samples treated as walls.
    Returns True if clear line exists between the two points.
"""
import heapq, math
from settings import COLS, ROWS, TILE_SIZE, MAZE_OFFSET_Y


def astar(game_map, start, goal):
    """Return (col,row) path from start→goal (start excluded). [] if none."""
    # Clamp goal to grid
    goal = (max(0, min(COLS-1, goal[0])),
            max(0, min(ROWS-1, goal[1])))

    # Clamp goal off wall
    if not game_map.walkable(*goal):
        for dc, dr in [(-1,0),(1,0),(0,-1),(0,1),
                       (-1,-1),(1,-1),(-1,1),(1,1)]:
            nb = (goal[0]+dc, goal[1]+dr)
            if (0 <= nb[0] < COLS and 0 <= nb[1] < ROWS
                    and game_map.walkable(*nb)):
                goal = nb
                break
        else:
            return []

    if start == goal:
        return []

    open_set  = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score   = {start: 0}

    while open_set:
        _, cur = heapq.heappop(open_set)
        if cur == goal:
            path = []
            while cur in came_from:
                path.append(cur)
                cur = came_from[cur]
            path.reverse()
            return path   # start tile excluded — enemy is already there

        cx, cy = cur
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nb = (cx+dx, cy+dy)
            if not (0 <= nb[0] < COLS and 0 <= nb[1] < ROWS):
                continue
            if not game_map.walkable(*nb):
                continue
            ng = g_score[cur] + 1
            if ng < g_score.get(nb, 1e9):
                came_from[nb] = cur
                g_score[nb]   = ng
                f = ng + abs(nb[0]-goal[0]) + abs(nb[1]-goal[1])
                heapq.heappush(open_set, (f, nb))

    return []


def has_los(game_map, ax, ay, bx, by):
    """True if straight line (ax,ay)→(bx,by) passes no walls."""
    dist = math.hypot(bx-ax, by-ay)
    if dist == 0:
        return True

    steps = max(1, int(dist // max(1, TILE_SIZE // 3)))

    for i in range(steps + 1):
        t  = i / steps
        px = ax + (bx - ax) * t
        py = ay + (by - ay) * t

        col = int(px // TILE_SIZE)
        row = int((py - MAZE_OFFSET_Y) // TILE_SIZE)

        if not (0 <= col < COLS and 0 <= row < ROWS):
            return False
        if game_map.is_wall(col, row):
            return False

    return True