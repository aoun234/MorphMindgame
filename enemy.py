# ─── enemy.py  v8.0 ──────────────────────────────────────────────
"""
4-state Enemy FSM  —  Final Production Version v8.0

WHY NOT Q-LEARNING:
  Q-Learning needs thousands of training episodes offline.
  It cannot learn meaningfully in a single game session (only ~200-500
  player moves available). The current Logistic Regression + Markov
  approach is exactly right for real-time in-session learning.
  The problem was never the algorithm — it was the activation conditions.

ROOT CAUSE OF PREDICT NEVER ACTIVATING (now fixed):
  Previous version required dist > _predict_min_dist AND LOS simultaneously.
  In a maze, when enemy has LOS the player is usually close (< 5 tiles).
  When player is far the enemy has no LOS. Both conditions were never
  true at the same time → PREDICT was unreachable.

FIX:
  Removed distance gate entirely. PREDICT now activates whenever:
    • predictor.trained == True
    • LOS is confirmed
    • player is in detect range
    • LR/Markov confidence >= threshold
  This is correct game design: prediction helps at ALL distances.
  Moving to where player WILL be is always better than chasing where
  they ARE, regardless of current distance.

STATE LOGIC:
  PATROL  → player never seen / memory expired. Random waypoints.
  CHASE   → LOS gained, ML not trained or confidence too low.
            Direct pixel pursuit at close range (no vibration).
  PREDICT → LOS gained + ML trained + confidence OK.
            Intercepts predicted position. 20% speed bonus.
  DETECT  → LOS lost after previously seeing player. Investigates LKP.
            Returns to PATROL if player not found at LKP.
"""
import pygame, math, random
from settings import *
from ai_system import astar, has_los

PATROL  = "PATROL"
DETECT  = "DETECT"
CHASE   = "CHASE"
PREDICT = "PREDICT"

STATE_COLOR = {
    PATROL : (110,  45,  45),
    DETECT : (210, 125,  20),
    CHASE  : (230,  40,  40),
    PREDICT: (148,  55, 215),
}
STATE_LABEL = {
    PATROL : "PATROL",
    DETECT : "DETECT",
    CHASE  : "CHASE",
    PREDICT: "ML-PRED",
}
ENEMY_COLORS = [RED, ORANGE, PURPLE, PINK, CYAN]

# ── Difficulty presets ────────────────────────────────────────────
# _conf_thresh: how confident ML must be before PREDICT activates
#   lower = more aggressive prediction use
#   higher = only predicts when very sure
_DIFF = {
    "easy": dict(
        detect_range=115, chase_spd=1.9,  patrol_spd=1.2,
        memory_frames=200, reaction_lock=22,
        chase_recalc=14,   predict_recalc=18,
        conf_thresh=0.55,  inv_wait=110,
    ),
    "medium": dict(
        detect_range=165, chase_spd=2.5,  patrol_spd=1.5,
        memory_frames=300, reaction_lock=12,
        chase_recalc=8,    predict_recalc=10,
        conf_thresh=0.44,  inv_wait=90,
    ),
    "hard": dict(
        detect_range=215, chase_spd=3.15, patrol_spd=1.95,
        memory_frames=500, reaction_lock=5,
        chase_recalc=4,    predict_recalc=6,
        conf_thresh=0.34,  inv_wait=45,
    ),
}

# Maps main.py difficulty strings → internal preset keys
_DIFF_MAP = {
    "EASY":   "easy",
    "NORMAL": "medium",
    "HARD":   "hard",
    "INSANE": "hard",
}


class Enemy:
    def __init__(self, col, row, idx=0,
                 patrol_spd=1.5, chase_spd=2.5,
                 damage=12, detect_range=160,
                 difficulty="medium"):

        self.col  = col
        self.row  = row
        self.idx  = idx
        self.x    = float(col * TILE_SIZE + TILE_SIZE // 2)
        self.y    = float(MAZE_OFFSET_Y + row * TILE_SIZE + TILE_SIZE // 2)

        self.base_color = ENEMY_COLORS[idx % len(ENEMY_COLORS)]
        self.state      = PATROL
        self.half       = ENEMY_SIZE // 2

        # Accept "HARD" (main.py) and "hard" (direct) both
        preset_key = _DIFF_MAP.get(difficulty, difficulty)
        p = _DIFF.get(preset_key, _DIFF["medium"])

        self.detect_range = p["detect_range"]
        self.chase_spd    = p["chase_spd"]
        self.patrol_spd   = p["patrol_spd"]
        self.damage       = damage

        # Internal difficulty params
        self._memory_frames  = p["memory_frames"]
        self._reaction_lock  = p["reaction_lock"]
        self._chase_recalc   = p["chase_recalc"]
        self._predict_recalc = p["predict_recalc"]
        self._conf_thresh    = p["conf_thresh"]
        self._inv_wait       = p["inv_wait"]

        # Path state
        self._path   = []
        self._pidx   = 0
        self._stuck  = 0
        self._recalc = 0

        # Patrol
        self._p_wait = random.randint(20, 60)
        self._p_dest = None

        # Last Known Position memory
        self._lkp_col   = col
        self._lkp_row   = row
        self._lkp_age   = 9999   # frames since last confirmed LOS

        # Awareness — enemy blind until first LOS contact
        self._ever_seen = False

        # DETECT investigation tracking
        self._inv_done = False

        # Combat cooldown
        self._atk_cd = 0

        # Hysteresis: min frames before state can change again
        self._lock = 0

        # Visuals
        self._bob    = random.uniform(0, 6.28)
        self._pulse  = random.uniform(0, 6.28)
        self._sparks = []
        self._nfont  = None

    # ═══════════════════════════════════════════════════════════════
    #  MAIN UPDATE
    # ═══════════════════════════════════════════════════════════════
    def update(self, player, game_map, predictor):
        dist = math.hypot(self.x - player.x, self.y - player.y)
        los  = has_los(game_map, self.x, self.y, player.x, player.y)

        # Awareness update — ONLY real LOS teaches the enemy
        if los and dist <= self.detect_range:
            self._lkp_col   = player.col
            self._lkp_row   = player.row
            self._lkp_age   = 0
            self._inv_done  = False
            self._ever_seen = True
        else:
            self._lkp_age = min(self._lkp_age + 1, 99999)

        # Melee attack
        if dist <= ENEMY_ATTACK_RANGE:
            self._do_attack(player)

        # FSM transition
        if self._lock > 0:
            self._lock -= 1
        else:
            self._fsm(dist, los, predictor, player)

        # Execute current state behaviour
        if   self.state == PATROL:  self._do_patrol(game_map)
        elif self.state == DETECT:  self._do_detect(player, game_map)
        elif self.state == CHASE:   self._do_chase(player, game_map)
        elif self.state == PREDICT: self._do_predict(player, game_map, predictor)

        # Tick timers
        if self._atk_cd > 0: self._atk_cd -= 1
        if self._recalc  > 0: self._recalc  -= 1

        # Visual animation tick
        self._bob    = (self._bob   + 0.09) % (2 * math.pi)
        self._pulse  = (self._pulse + 0.06) % (2 * math.pi)
        self._sparks = [(x+vx, y+vy, vx*0.88, vy*0.88, l-1, c)
                        for x,y,vx,vy,l,c in self._sparks if l > 0]

    # ═══════════════════════════════════════════════════════════════
    #  FSM  — priority ladder
    # ═══════════════════════════════════════════════════════════════
    def _fsm(self, dist, los, predictor, player):
        in_range     = dist <= self.detect_range
        memory_alive = self._lkp_age < self._memory_frames

        # ── PRIORITY 1: visible + in range → combat ──────────────
        if in_range and los:
            # Use PREDICT when ML is ready and confident enough
            # NO distance gate — prediction helps at all ranges
            if predictor.trained and self._ml_confident(predictor, player):
                self._goto(PREDICT)
            else:
                self._goto(CHASE)
            return

        # ── PRIORITY 2: lost LOS after seeing player → DETECT ────
        if not los and self._ever_seen and memory_alive:
            if self.state in (CHASE, PREDICT):
                # Just lost sight — go investigate LKP immediately
                self._goto(DETECT)
                return
            if self.state == DETECT:
                # Already investigating — _do_detect handles it
                return
            # Was in PATROL but LKP is fresh (recently spotted)
            if self._lkp_age < self._reaction_lock * 4:
                self._goto(DETECT)
                return

        # ── PRIORITY 3: memory gone or never saw player → PATROL ─
        if not memory_alive or not self._ever_seen:
            self._goto(PATROL)

    def _ml_confident(self, predictor, player):
        """
        Returns True when ML model is confident enough to use PREDICT.

        Uses the stored scaler from ml_model.py to normalise features,
        then checks max class probability against difficulty threshold.

        Falls back to False on any error → CHASE is used safely.
        """
        if not predictor.trained:
            return False
        try:
            import numpy as np
            from ml_model import WINDOW
            hist = list(player.move_history)
            if len(hist) < WINDOW:
                return False

            feat = np.array(hist[-WINDOW:]).reshape(1, -1)

            # If LR model and scaler are available, use them
            if predictor.model is not None and predictor.scaler is not None:
                feats = predictor.scaler.transform(feat)
                proba = predictor.model.predict_proba(feats)[0]
                return float(max(proba)) >= self._conf_thresh

            # Markov-only mode: use stored confidence (mean LR train accuracy)
            # For Markov we use a lower fixed threshold since it is less precise
            return predictor.confidence >= 0.30

        except Exception:
            return False

    def _goto(self, new_state):
        """Transition; reset path; set hysteresis lock."""
        if self.state == new_state:
            return
        self.state   = new_state
        self._path   = []
        self._pidx   = 0
        self._recalc = 0
        self._lock   = self._reaction_lock

    # ═══════════════════════════════════════════════════════════════
    #  STATE BEHAVIOURS
    # ═══════════════════════════════════════════════════════════════

    # ── PATROL ────────────────────────────────────────────────────
    def _do_patrol(self, gm):
        if self._p_wait > 0:
            self._p_wait -= 1
            return
        if self._path and self._pidx < len(self._path):
            if not self._walk(self.patrol_spd):
                self._p_wait = random.randint(50, 130)
                self._path   = []
                self._p_dest = None
            return
        for _ in range(40):
            tc, tr = gm.random_floor()
            if abs(tc - self.col) + abs(tr - self.row) >= 5:
                break
        self._p_dest = (tc, tr)
        self._path   = self._get_path(gm, self.col, self.row, tc, tr)
        self._pidx   = 0

    # ── DETECT ────────────────────────────────────────────────────
    def _do_detect(self, player, gm):
        """Navigate to Last Known Position. On arrival, pause then give up."""
        tc, tr = self._lkp_col, self._lkp_row

        if self._recalc <= 0 or not self._path or self._pidx >= len(self._path):
            self._path   = self._get_path(gm, self.col, self.row, tc, tr)
            self._pidx   = 0
            self._recalc = 30

        self._walk(self.patrol_spd * 0.95)

        arrived = (self.col == tc and self.row == tr)
        if arrived and (not self._path or self._pidx >= len(self._path)):
            if not self._inv_done:
                self._inv_done = True
                self._p_wait   = self._inv_wait
                # Expire memory → FSM will transition to PATROL next tick
                self._lkp_age  = self._memory_frames + 1

    # ── CHASE ─────────────────────────────────────────────────────
    def _do_chase(self, player, gm):
        """
        Two-zone pursuit eliminates tile-snap vibration:
          ≤ 1.5 tiles : direct pixel movement toward player
          > 1.5 tiles : A* path following, recalculated every N frames
        """
        px_dist = math.hypot(self.x - player.x, self.y - player.y)

        if px_dist <= TILE_SIZE * 1.5:
            self._direct_move(player.x, player.y, self.chase_spd)
            self._recalc = 0
            return

        if self._recalc <= 0:
            self._path   = self._get_path(gm, self.col, self.row,
                                          player.col, player.row)
            self._pidx   = 0
            self._recalc = self._chase_recalc

        self._walk(self.chase_spd)

    # ── PREDICT ───────────────────────────────────────────────────
    def _do_predict(self, player, gm, predictor):
        """
        ML-assisted intercept. Predicts where player is heading and
        moves to cut them off. 20% speed bonus over CHASE.

        Same close-range direct movement as CHASE to prevent vibration.
        Falls back to direct player position if intercept == own tile.
        """
        px_dist = math.hypot(self.x - player.x, self.y - player.y)
        predict_speed = self.chase_spd * 1.20

        if px_dist <= TILE_SIZE * 1.5:
            self._direct_move(player.x, player.y, predict_speed)
            self._recalc = 0
            return

        if self._recalc <= 0:
            direction = predictor.predict(player.move_history)
            dc, dr    = predictor.dir_to_delta(direction)

            # Project intercept forward up to 8 tiles on predicted path
            ic, ir = player.col, player.row
            for steps in range(8, 0, -1):
                tc2 = player.col + dc * steps
                tr2 = player.row + dr * steps
                if (0 <= tc2 < COLS and 0 <= tr2 < ROWS
                        and not gm.is_wall(tc2, tr2)):
                    ic, ir = tc2, tr2
                    break

            # Intercept == own tile means we're already blocking; chase directly
            if ic == self.col and ir == self.row:
                ic, ir = player.col, player.row

            self._path   = self._get_path(gm, self.col, self.row, ic, ir)
            self._pidx   = 0
            self._recalc = self._predict_recalc

        self._walk(predict_speed)

    # ═══════════════════════════════════════════════════════════════
    #  MOVEMENT CORE
    # ═══════════════════════════════════════════════════════════════

    def _direct_move(self, tx, ty, speed):
        """
        Pixel-level movement toward (tx, ty). Clears A* path so
        _walk() does not run on stale waypoints.
        Used when player is within 1.5 tiles — eliminates vibration.
        """
        dx = tx - self.x
        dy = ty - self.y
        d  = math.hypot(dx, dy)
        if d > 0.5:
            self.x += (dx / d) * speed
            self.y += (dy / d) * speed
        self._path  = []
        self._pidx  = 0
        self._stuck = 0
        self._sync_tile()

    def _walk(self, speed):
        """
        Advance along A* path at `speed` px/frame.
        Returns True while travelling, False when path exhausted.
        """
        if not self._path or self._pidx >= len(self._path):
            return False

        tc, tr = self._path[self._pidx]
        tx = tc * TILE_SIZE + TILE_SIZE // 2
        ty = MAZE_OFFSET_Y + tr * TILE_SIZE + TILE_SIZE // 2

        dx   = tx - self.x
        dy   = ty - self.y
        dist = math.hypot(dx, dy)

        if dist <= speed + 0.5:
            self.x, self.y = float(tx), float(ty)
            self._pidx    += 1
            self._stuck    = 0
        else:
            self.x += (dx / dist) * speed
            self.y += (dy / dist) * speed
            self._stuck += 1
            if self._stuck > 80:        # ~1.3s stuck → force recalc
                self._path   = []
                self._pidx   = 0
                self._recalc = 0
                self._stuck  = 0

        self._sync_tile()
        return self._pidx < len(self._path)

    def _sync_tile(self):
        """Keep col/row consistent with pixel position."""
        self.col = max(0, min(COLS - 1, int(self.x // TILE_SIZE)))
        self.row = max(0, min(ROWS - 1,
                              int((self.y - MAZE_OFFSET_Y) // TILE_SIZE)))

    def _get_path(self, gm, sc, sr, tc, tr):
        """A* with wall-aware target clamping."""
        tc = max(0, min(COLS - 1, tc))
        tr = max(0, min(ROWS - 1, tr))
        if gm.is_wall(tc, tr):
            for dc, dr in [(0,1),(0,-1),(1,0),(-1,0),
                           (1,1),(-1,-1),(1,-1),(-1,1)]:
                nc, nr = tc + dc, tr + dr
                if 0 <= nc < COLS and 0 <= nr < ROWS and not gm.is_wall(nc, nr):
                    tc, tr = nc, nr
                    break
            else:
                return []
        return astar(gm, (sc, sr), (tc, tr))

    def _do_attack(self, player):
        if self._atk_cd <= 0:
            player.take_damage(self.damage)
            self._atk_cd = ENEMY_ATTACK_CD
            for _ in range(10):
                vx = random.uniform(-3.5, 3.5)
                vy = random.uniform(-4.5, -0.5)
                self._sparks.append((self.x, self.y, vx, vy, 28, ORANGE))

    # ═══════════════════════════════════════════════════════════════
    #  DRAWING
    # ═══════════════════════════════════════════════════════════════
    @property
    def rect(self):
        return pygame.Rect(self.x - self.half, self.y - self.half,
                           ENEMY_SIZE, ENEMY_SIZE)

    def draw(self, surf):
        bx = int(self.x)
        by = int(self.y + math.sin(self._bob) * 1.5)
        c  = STATE_COLOR.get(self.state, self.base_color)
        h  = self.half

        if self.state == PATROL:
            r  = 26
            rg = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(rg, (*c, 30), (r, r), r, 2)
            surf.blit(rg, (bx - r, by - r))

        elif self.state == DETECT:
            r  = int(self.detect_range * 0.65)
            rg = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            for ang in range(0, 360, 20):
                rad = math.radians(ang + self._pulse * 180 / math.pi * 2)
                rx  = r + int((r - 4) * math.cos(rad))
                ry  = r + int((r - 4) * math.sin(rad))
                pygame.draw.circle(rg, (*ORANGE, 110), (rx, ry), 3)
            surf.blit(rg, (bx - r, by - r))
            if self._nfont is None:
                self._nfont = pygame.font.SysFont("consolas", 13, bold=True)
            ql = self._nfont.render("?", True, ORANGE)
            ql.set_alpha(200)
            surf.blit(ql, (bx - ql.get_width()//2, by - h - 22))

        elif self.state == CHASE:
            r  = self.detect_range
            rg = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(rg, (*RED, 10), (r, r), r)
            pygame.draw.circle(rg, (*RED, 65), (r, r), r, 2)
            surf.blit(rg, (bx - r, by - r))
            if self._nfont is None:
                self._nfont = pygame.font.SysFont("consolas", 13, bold=True)
            ql = self._nfont.render("!", True, RED)
            surf.blit(ql, (bx - ql.get_width()//2, by - h - 22))

        elif self.state == PREDICT:
            r  = self.detect_range
            pr = r + int(6 * math.sin(self._pulse * 3))
            rg = pygame.Surface((pr*2, pr*2), pygame.SRCALPHA)
            pygame.draw.circle(rg, (*PURPLE, 14), (pr, pr), pr)
            pygame.draw.circle(rg, (*PURPLE, 75), (pr, pr), pr, 2)
            surf.blit(rg, (bx - pr, by - pr))
            if self._nfont is None:
                self._nfont = pygame.font.SysFont("consolas", 11, bold=True)
            ql = self._nfont.render("ML", True, PURPLE)
            surf.blit(ql, (bx - ql.get_width()//2, by - h - 22))

        # Glow halo
        gr   = h + 5 + int(2 * math.sin(self._pulse))
        glow = pygame.Surface((gr*4, gr*4), pygame.SRCALPHA)
        ga   = 60 if self.state in (CHASE, PREDICT) else 22
        pygame.draw.circle(glow, (*c, ga), (gr*2, gr*2), gr)
        surf.blit(glow, (bx - gr*2, by - gr*2))

        # Shadow
        sh = pygame.Surface((h*2+6, 7), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 60), (0, 0, h*2+6, 7))
        surf.blit(sh, (bx - h - 3, by + h - 2))

        # Body
        dark = (max(0, c[0]-65), max(0, c[1]-65), max(0, c[2]-65))
        pygame.draw.circle(surf, dark, (bx, by), h + 2)
        pygame.draw.circle(surf, c,    (bx, by), h)
        shs = pygame.Surface((h, h), pygame.SRCALPHA)
        pygame.draw.circle(shs, (255, 255, 255, 55), (h//3, h//3), h//3)
        surf.blit(shs, (bx - h//2, by - h//2))

        # Eyes
        pc = (220, 20, 20) if self.state in (CHASE, PREDICT) else (70, 70, 70)
        for ox in [-5, 5]:
            ex, ey = bx + ox, by - 4
            pygame.draw.circle(surf, WHITE,  (ex, ey), 4)
            pygame.draw.circle(surf, pc,     (ex, ey), 2)
            pygame.draw.circle(surf, WHITE,  (ex+1, ey-1), 1)

        # Number badge
        if self._nfont is None:
            self._nfont = pygame.font.SysFont("consolas", 11, bold=True)
        nl = self._nfont.render(str(self.idx + 1), True, WHITE)
        surf.blit(nl, (bx - nl.get_width()//2, by + h - nl.get_height()))

        # Attack sparks
        for px2, py2, vx, vy, l, pc2 in self._sparks:
            a  = min(255, int(255 * l / 28))
            ss = pygame.Surface((5, 5), pygame.SRCALPHA)
            pygame.draw.circle(ss, (*pc2, a), (2, 2), 2)
            surf.blit(ss, (int(px2)-2, int(py2)-2))

    def draw_state_tag(self, surf, fnt):
        lbl = STATE_LABEL.get(self.state, "?")
        c   = STATE_COLOR.get(self.state, WHITE)
        txt = fnt.render(lbl, True, c)
        tx  = int(self.x) - txt.get_width() // 2
        ty  = int(self.y) - self.half - 34
        bg  = pygame.Surface((txt.get_width() + 8, 14), pygame.SRCALPHA)
        bg.fill((*c, 42))
        pygame.draw.rect(bg, (*c, 170), (0, 0, bg.get_width(), 14),
                         1, border_radius=3)
        surf.blit(bg,  (tx - 4, ty))
        surf.blit(txt, (tx, ty + 1))