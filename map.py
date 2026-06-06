# ─── map.py  v3.1 ────────────────────────────────────────────────
# Maze is drawn offset by MAZE_OFFSET_Y so header stays clear.
import pygame, random
from settings import *

def tile_rect(col, row):
    return pygame.Rect(col*TILE_SIZE,
                       MAZE_OFFSET_Y + row*TILE_SIZE,
                       TILE_SIZE, TILE_SIZE)

class GameMap:
    def __init__(self, level=1):
        idx = min(level-1, len(MAZES)-1)
        self.grid = [row[:] for row in MAZES[idx]]
        self._build_rects()
        self.floor_tiles = [
            (c, r) for r in range(ROWS) for c in range(COLS)
            if self.grid[r][c] == 0
        ]
        self._surf = None
        self._render()

    def _build_rects(self):
        self.wall_rects = [tile_rect(c,r)
                           for r in range(ROWS) for c in range(COLS)
                           if self.grid[r][c]==1]

    def _render(self):
        self._surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._surf.fill(BG)
        # Header strip
        pygame.draw.rect(self._surf, HEADER_BG, (0,0,SCREEN_WIDTH,MAZE_OFFSET_Y))
        # Footer strip
        pygame.draw.rect(self._surf, FOOTER_BG,
                         (0, MAZE_OFFSET_Y+MAZE_H, SCREEN_WIDTH, FOOTER_H))
        # Separator lines
        pygame.draw.line(self._surf, (40,48,72),
                         (0,MAZE_OFFSET_Y),(SCREEN_WIDTH,MAZE_OFFSET_Y), 2)
        pygame.draw.line(self._surf, (40,48,72),
                         (0,MAZE_OFFSET_Y+MAZE_H),(SCREEN_WIDTH,MAZE_OFFSET_Y+MAZE_H), 2)
        # Tiles
        for r in range(ROWS):
            for c in range(COLS):
                rect = tile_rect(c, r)
                if self.grid[r][c] == 1:
                    pygame.draw.rect(self._surf, WALL_COLOR, rect)
                    pygame.draw.line(self._surf, WALL_EDGE,
                                     rect.topleft, rect.topright, 1)
                    pygame.draw.line(self._surf, WALL_EDGE,
                                     rect.topleft, rect.bottomleft, 1)
                else:
                    pygame.draw.rect(self._surf, FLOOR_COLOR, rect)
                    pygame.draw.rect(self._surf, FLOOR_LINE, rect, 1)

    def is_wall(self, col, row):
        if col<0 or col>=COLS or row<0 or row>=ROWS: return True
        return self.grid[row][col] == 1

    def walkable(self, col, row): return not self.is_wall(col, row)

    def random_floor(self, exclude=None):
        ex = exclude or []
        return random.choice([t for t in self.floor_tiles if t not in ex])

    def draw(self, surface):
        surface.blit(self._surf, (0,0))

    def col_row_to_px(self, col, row):
        """Centre pixel of a tile."""
        return (col*TILE_SIZE + TILE_SIZE//2,
                MAZE_OFFSET_Y + row*TILE_SIZE + TILE_SIZE//2)