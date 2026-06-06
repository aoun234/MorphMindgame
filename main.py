# ─── main.py  v3.1 ───────────────────────────────────────────────
"""
MorphMind AI  –  Maze Escape  v3.1
Layout: [HEADER 52px][MAZE 570px][FOOTER 44px]
Nothing overlaps the maze.
"""
import sys, math, random
import pygame
from settings import *
from map      import GameMap
from player   import Player
from enemy    import Enemy
from ml_model import MovementPredictor

pygame.init()
pygame.font.init()

# ── Font cache ────────────────────────────────────────────────────
_FC = {}
def font(size, bold=True):
    k=(size,bold)
    if k not in _FC: _FC[k]=pygame.font.SysFont("consolas",size,bold=bold)
    return _FC[k]

# ═══════════════════════════════════════════════════════════════════
#  UI helpers
# ═══════════════════════════════════════════════════════════════════
def panel(surf, x, y, w, h, alpha=215, radius=6, border=(50,62,96)):
    s=pygame.Surface((w,h),pygame.SRCALPHA)
    s.fill((10,13,24,alpha))
    pygame.draw.rect(s,(*border,200),(0,0,w,h),1,border_radius=radius)
    surf.blit(s,(x,y))

def button(surf, txt, rect, hov=False, col=ACCENT, fsize=18):
    bg=(40,52,78) if hov else (16,20,38)
    bd=col if hov else (50,62,96)
    s=pygame.Surface((rect.w,rect.h),pygame.SRCALPHA)
    s.fill((*bg,230))
    pygame.draw.rect(s,(*bd,255),(0,0,rect.w,rect.h),2,border_radius=7)
    surf.blit(s,(rect.x,rect.y))
    lbl=font(fsize).render(txt,True,col if hov else LIGHT_GRAY)
    surf.blit(lbl,(rect.centerx-lbl.get_width()//2,
                   rect.centery-lbl.get_height()//2))

def hbar(surf, x, y, w, h, pct, fg, bg=(25,30,50)):
    pygame.draw.rect(surf,bg,(x,y,w,h),border_radius=h//2)
    if pct>0: pygame.draw.rect(surf,fg,(x,y,int(w*pct),h),border_radius=h//2)
    pygame.draw.rect(surf,(55,65,100),(x,y,w,h),1,border_radius=h//2)

# ═══════════════════════════════════════════════════════════════════
#  Collectibles
# ═══════════════════════════════════════════════════════════════════
class Key:
    def __init__(self,col,row):
        self.col=col; self.row=row
        self.x=col*TILE_SIZE+TILE_SIZE//2
        self.y=MAZE_OFFSET_Y+row*TILE_SIZE+TILE_SIZE//2
        self.picked=False; self._t=random.uniform(0,6.28)
    def update(self): self._t+=0.07
    def draw(self,surf):
        if self.picked: return
        by=self.y+int(3*math.sin(self._t))
        g=pygame.Surface((36,36),pygame.SRCALPHA)
        pygame.draw.circle(g,(240,200,30,55),(18,18),17)
        surf.blit(g,(self.x-18,by-18))
        pygame.draw.circle(surf,YELLOW,(self.x,by),KEY_SIZE+3)
        pygame.draw.circle(surf,DARK_GRAY,(self.x,by),KEY_SIZE+1)
        pygame.draw.circle(surf,YELLOW,(self.x,by),KEY_SIZE-1)
        pygame.draw.circle(surf,(255,245,120),(self.x-2,by-3),3)

class ExitPortal:
    def __init__(self,col,row):
        self.col=col; self.row=row
        self.x=col*TILE_SIZE+TILE_SIZE//2
        self.y=MAZE_OFFSET_Y+row*TILE_SIZE+TILE_SIZE//2
        self.open=False; self._t=0.0
    def update(self): self._t+=0.04
    def draw(self,surf):
        r=EXIT_SIZE//2+int(3*math.sin(self._t))
        c=CYAN if self.open else GRAY
        g=pygame.Surface((r*4,r*4),pygame.SRCALPHA)
        pygame.draw.circle(g,(*c,45),(r*2,r*2),r*2)
        surf.blit(g,(self.x-r*2,self.y-r*2))
        pygame.draw.circle(surf,DARK_GRAY,(self.x,self.y),r+3)
        pygame.draw.circle(surf,c,(self.x,self.y),r)
        pygame.draw.circle(surf,DARK_GRAY,(self.x,self.y),r-6)
        if self.open:
            for i in range(6):
                a=self._t+i*math.pi/3
                pygame.draw.circle(surf,WHITE,
                    (self.x+int((r-3)*math.cos(a)),
                     self.y+int((r-3)*math.sin(a))),3)
        lbl=font(10).render("EXIT" if self.open else "LOCKED",True,c)
        surf.blit(lbl,(self.x-lbl.get_width()//2,self.y-r-14))

class Powerup:
    TYPES=["speed","shield","health"]
    COLORS={"speed":ACCENT,"shield":CYAN,"health":GREEN}
    LABELS={"speed":"SPEED","shield":"SHIELD","health":"+HP"}
    def __init__(self,col,row,kind=None):
        self.col=col; self.row=row
        self.x=col*TILE_SIZE+TILE_SIZE//2
        self.y=MAZE_OFFSET_Y+row*TILE_SIZE+TILE_SIZE//2
        self.kind=kind or random.choice(self.TYPES)
        self.collected=False; self._t=random.uniform(0,6.28)
    def update(self): self._t+=0.06
    def draw(self,surf):
        if self.collected: return
        by=self.y+int(3*math.sin(self._t))
        c=self.COLORS[self.kind]
        g=pygame.Surface((34,34),pygame.SRCALPHA)
        pygame.draw.circle(g,(*c,55),(17,17),16)
        surf.blit(g,(self.x-17,by-17))
        pygame.draw.circle(surf,DARK_GRAY,(self.x,by),POWERUP_SIZE+3)
        pygame.draw.circle(surf,c,(self.x,by),POWERUP_SIZE)
        lbl=font(10).render(self.LABELS[self.kind],True,c)
        surf.blit(lbl,(self.x-lbl.get_width()//2,by-POWERUP_SIZE-13))

class FloatText:
    def __init__(self,x,y,txt,col=WHITE):
        self.x=float(x); self.y=float(y)
        self.txt=txt; self.col=col; self.life=80
    def update(self): self.y-=0.7; self.life-=1
    def draw(self,surf):
        if self.life<=0: return
        s=font(13).render(self.txt,True,self.col)
        s.set_alpha(min(255,self.life*4))
        surf.blit(s,(int(self.x)-s.get_width()//2,int(self.y)))

# ═══════════════════════════════════════════════════════════════════
#  Alert flash (top-centre of maze, not overlapping header/footer)
# ═══════════════════════════════════════════════════════════════════
class Alerts:
    def __init__(self): self._q=[]
    def push(self,txt,col=RED):
        for a in self._q:
            if a[0]==txt: return
        self._q.append([txt,col,110])
    def update(self):
        self._q=[[t,c,l-1] for t,c,l in self._q if l>0]
    def draw(self,surf):
        for i,(t,c,l) in enumerate(self._q[:3]):
            a=min(255,l*5)
            lbl=font(14).render(t,True,c)
            x=SCREEN_WIDTH//2-lbl.get_width()//2
            y=MAZE_OFFSET_Y+8+i*26
            bg=pygame.Surface((lbl.get_width()+18,22),pygame.SRCALPHA)
            bg.fill((*c,28)); pygame.draw.rect(bg,(*c,140),(0,0,bg.get_width(),22),1,border_radius=4)
            bg.set_alpha(a); surf.blit(bg,(x-9,y-2)); lbl.set_alpha(a); surf.blit(lbl,(x,y+1))

# ═══════════════════════════════════════════════════════════════════
#  Minimap (inside footer, right side)
# ═══════════════════════════════════════════════════════════════════
class Minimap:
    S=2
    W=COLS*S; H=ROWS*S
    def draw(self,surf,gmap,player,enemies,keys,exit_obj):
        fx=SCREEN_WIDTH-self.W-10
        fy=MAZE_OFFSET_Y+MAZE_H+4
        panel(surf,fx-2,fy-2,self.W+4,self.H+4,alpha=230)
        s=self.S
        for r in range(ROWS):
            for c in range(COLS):
                col=WALL_COLOR if gmap.grid[r][c]==1 else FLOOR_COLOR
                pygame.draw.rect(surf,col,(fx+c*s,fy+r*s,s,s))
        for k in keys:
            if not k.picked: pygame.draw.rect(surf,YELLOW,(fx+k.col*s,fy+k.row*s,s,s))
        ec=CYAN if exit_obj.open else GRAY
        pygame.draw.rect(surf,ec,(fx+exit_obj.col*s,fy+exit_obj.row*s,s,s))
        SCOL={"PATROL":(170,55,55),"DETECT":ORANGE,"CHASE":RED,"PREDICT":PURPLE}
        for e in enemies:
            pygame.draw.rect(surf,SCOL.get(e.state,RED),(fx+e.col*s,fy+e.row*s,s,s))
        pygame.draw.rect(surf,GREEN,(fx+player.col*s,fy+player.row*s,s,s))

# ═══════════════════════════════════════════════════════════════════
#  HEADER  (top 52px)
#  [HP bar + key pips | Level/Score centre | Difficulty badge right]
# ═══════════════════════════════════════════════════════════════════
def draw_header(surf, player, kn, level, max_level, difficulty, score):
    # Background + separator already drawn by map
    H=MAZE_OFFSET_Y
    cx=SCREEN_WIDTH//2

    # ── Left: HP bar + key pips ───────────────────────────────────
    panel(surf,6,6,230,H-10,alpha=220)
    pct=max(0,player.health/player.max_health)
    hpc=GREEN if pct>0.5 else ORANGE if pct>0.25 else RED
    hbar(surf,14,12,210,12,pct,hpc)
    hp_lbl=font(11).render(f"HP  {player.health}/{player.max_health}",True,WHITE)
    surf.blit(hp_lbl,(14,26))
    # Key pips
    for i in range(kn):
        kx=14+i*22; ky=40
        filled=(i<player.keys)
        pygame.draw.circle(surf,YELLOW if filled else (45,50,75),(kx,ky),7)
        if filled: pygame.draw.circle(surf,WHITE,(kx,ky),3)
        else: pygame.draw.circle(surf,(70,80,110),(kx,ky),7,1)

    # ── Centre: Level title ───────────────────────────────────────
    lt=font(22).render(f"LEVEL  {level} / {max_level}",True,ACCENT)
    surf.blit(lt,(cx-lt.get_width()//2, H//2-lt.get_height()//2))

    # ── Right: Difficulty + Score ─────────────────────────────────
    panel(surf,SCREEN_WIDTH-240,6,234,H-10,alpha=220)
    dc={"EASY":GREEN,"NORMAL":YELLOW,"HARD":ORANGE,"INSANE":RED}.get(difficulty,WHITE)
    dl=font(12).render(difficulty,True,dc)
    sl=font(14).render(f"SCORE  {score:07d}",True,CYAN)
    surf.blit(dl,(SCREEN_WIDTH-234,10))
    surf.blit(sl,(SCREEN_WIDTH-234,26))

    # Powerup pills
    px2=SCREEN_WIDTH-234; py2=42
    if player.speed_boost>0:
        pl=font(10).render(f"SPEED {player.speed_boost//60+1}s",True,ACCENT)
        surf.blit(pl,(px2,py2)); px2+=pl.get_width()+12
    if player.shield>0:
        pl=font(10).render(f"SHIELD {player.shield//60+1}s",True,CYAN)
        surf.blit(pl,(px2,py2))

# ═══════════════════════════════════════════════════════════════════
#  FOOTER  (bottom 44px)
#  [ML panel left | controls centre | enemy tracker right]
# ═══════════════════════════════════════════════════════════════════
STATE_COL={"PATROL":(170,55,55),"DETECT":ORANGE,"CHASE":RED,"PREDICT":PURPLE}
# State display info
_STATE_FULL  = {"PATROL":"PATROL","DETECT":"DETECT","CHASE":"CHASE","PREDICT":"ML-PRED"}
_STATE_COLOR = {"PATROL":(155,55,55),"DETECT":(220,130,30),"CHASE":(228,52,52),"PREDICT":(158,68,220)}

def draw_footer(surf, predictor, player, enemies):
    fy = MAZE_OFFSET_Y + MAZE_H + 2
    fh = FOOTER_H - 4

    # ── Left: ML panel (fixed width 240) ─────────────────────────
    ml_w = 240
    panel(surf, 6, fy, ml_w, fh, alpha=225)

    dot_c = GREEN if predictor.trained else (80,80,80)
    pygame.draw.circle(surf, dot_c, (16, fy+8), 5)

    if predictor.trained:
        conf = getattr(predictor, "confidence_pct", 0)
        darr = {0:"STILL",1:"UP",2:"DOWN",3:"LEFT",4:"RIGHT"}.get(predictor.last_pred,"?")
        t1 = font(11).render("ML  ACTIVE", True, CYAN)
        t2 = font(11).render(f"Conf:{conf}%  Next:{darr}", True, PURPLE)
        surf.blit(t1, (24, fy+3))
        surf.blit(t2, (24, fy+17))
        hbar(surf, 24, fy+31, ml_w-28, 5, conf/100, CYAN)
    else:
        smp = len(player.move_history)
        t1 = font(11).render("ML  LEARNING", True, GRAY)
        t2 = font(11).render(f"Data: {smp}/{ML_MIN_SAMPLES}", True, LIGHT_GRAY)
        surf.blit(t1, (24, fy+3))
        surf.blit(t2, (24, fy+17))
        hbar(surf, 24, fy+31, ml_w-28, 5, min(1.0,smp/ML_MIN_SAMPLES), ORANGE)

    # ── Centre: controls hint ────────────────────────────────────
    hints = [("WASD",ACCENT),(" Move  ",LIGHT_GRAY),
             ("P",ACCENT),(" Pause  ",LIGHT_GRAY),
             ("ESC",ACCENT),(" Menu",LIGHT_GRAY)]
    hx = ml_w + 18
    hy = fy + fh//2 - 7
    for txt, col in hints:
        s = font(11).render(txt, True, col)
        surf.blit(s, (hx, hy))
        hx += s.get_width()

    # ── Right: Enemy Tracker ─────────────────────────────────────
    # Each card: 108px wide — shows number, state, dist bar, speed dot
    n      = len(enemies)
    cw     = 108
    gap    = 4
    ew     = n * cw + (n-1)*gap + 8
    ex0    = SCREEN_WIDTH - ew - 6

    panel(surf, ex0, fy, ew, fh, alpha=225)

    for i, e in enumerate(enemies):
        cx2 = ex0 + 4 + i*(cw+gap)
        cy2 = fy + 2
        ch  = fh - 4

        sc   = _STATE_COLOR.get(e.state, (155,55,55))
        slbl = _STATE_FULL.get(e.state, "?")

        # Card background tinted by state color
        card = pygame.Surface((cw, ch), pygame.SRCALPHA)
        card.fill((*sc, 28))
        pygame.draw.rect(card, (*sc, 170), (0,0,cw,ch), 1, border_radius=4)
        surf.blit(card, (cx2, cy2))

        # Left color bar
        pygame.draw.rect(surf, sc, (cx2+1, cy2+3, 3, ch-6), border_radius=2)

        # Enemy number  "E1"
        en_lbl = font(12).render(f"E{e.idx+1}", True, WHITE)
        surf.blit(en_lbl, (cx2+7, cy2+3))

        # Enemy body color dot
        pygame.draw.circle(surf, e.base_color, (cx2+30, cy2+6), 5)

        # State label  "CHASE"
        st_lbl = font(10).render(slbl, True, sc)
        surf.blit(st_lbl, (cx2+38, cy2+3))

        # ── Distance to player bar ─────────────────────────────
        dist     = math.hypot(e.x - player.x, e.y - player.y)
        max_dist = float(e.detect_range * 2.0)
        prox_pct = max(0.0, min(1.0, 1.0 - dist/max_dist))   # 1=close 0=far
        bar_col  = RED if prox_pct>0.7 else ORANGE if prox_pct>0.4 else GREEN
        hbar(surf, cx2+6, cy2+ch-14, cw-12, 6, prox_pct, bar_col)

        # Tiny "DIST" label under bar
        dl = font(9).render("DIST", True, GRAY)
        surf.blit(dl, (cx2+6, cy2+ch-24))

        # Speed indicator dot (moving = bright, idle = dim)
        spd = e.chase_spd if e.state in ("CHASE","PREDICT") else (
              e.patrol_spd*0.7 if e.state=="DETECT" else e.patrol_spd)
        max_spd  = e.chase_spd * 1.2
        spd_pct  = min(1.0, spd/max_spd)
        spd_col  = RED if spd_pct>0.8 else ORANGE if spd_pct>0.5 else GRAY
        pygame.draw.circle(surf, spd_col, (cx2+cw-10, cy2+6), 4)
        pygame.draw.circle(surf, WHITE,   (cx2+cw-10, cy2+6), 4, 1)

# ═══════════════════════════════════════════════════════════════════
#  Main Menu
# ═══════════════════════════════════════════════════════════════════
class MenuScreen:
    def __init__(self,screen):
        self.screen=screen; self._t=0.0
        self._stars=[(random.randint(0,SCREEN_WIDTH),
                      random.randint(0,SCREEN_HEIGHT),
                      random.uniform(0.3,1.4)) for _ in range(100)]
    def run(self):
        clock=pygame.time.Clock()
        btns={"play":pygame.Rect(SCREEN_WIDTH//2-130,300,260,50),
              "quit":pygame.Rect(SCREEN_WIDTH//2-130,366,260,50)}
        while True:
            mx,my=pygame.mouse.get_pos()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
                if ev.type==pygame.KEYDOWN:
                    if ev.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                    if ev.key==pygame.K_RETURN: return
                if ev.type==pygame.MOUSEBUTTONDOWN:
                    if btns["play"].collidepoint(mx,my): return
                    if btns["quit"].collidepoint(mx,my): pygame.quit(); sys.exit()
            self._draw(btns,mx,my); clock.tick(FPS)

    def _draw(self,btns,mx,my):
        self._t+=0.018; self.screen.fill(BG)
        for sx,sy,sp in self._stars:
            raw=65+105*math.sin(self._t*sp)
            b=max(0,min(255,int(raw))); b2=max(0,min(255,int(raw+35)))
            pygame.draw.circle(self.screen,(b,b,b2),(sx,sy),1)
        # Glow title
        for ox,oy,a in [(-2,0,35),(2,0,35),(0,-2,35),(0,2,35)]:
            g=font(46).render("MORPHMIND  AI",True,ACCENT2)
            g.set_alpha(a)
            self.screen.blit(g,(SCREEN_WIDTH//2-g.get_width()//2+ox,
                                145+oy+int(5*math.sin(self._t))))
        t1=font(46).render("MORPHMIND  AI",True,ACCENT)
        sub=font(20).render("M A Z E   E S C A P E",True,LIGHT_GRAY)
        ver=font(11).render("v3.1  |  AI + ML Edition",True,GRAY)
        self.screen.blit(t1,(SCREEN_WIDTH//2-t1.get_width()//2,145+int(5*math.sin(self._t))))
        self.screen.blit(sub,(SCREEN_WIDTH//2-sub.get_width()//2,210))
        pygame.draw.line(self.screen,(40,50,80),(SCREEN_WIDTH//2-200,258),(SCREEN_WIDTH//2+200,258),1)
        button(self.screen,"PLAY",btns["play"],btns["play"].collidepoint(mx,my),ACCENT,22)
        button(self.screen,"QUIT",btns["quit"],btns["quit"].collidepoint(mx,my),RED,18)
        self.screen.blit(ver,(SCREEN_WIDTH//2-ver.get_width()//2,SCREEN_HEIGHT-22))
        pygame.display.flip()

# ═══════════════════════════════════════════════════════════════════
#  Difficulty Screen
# ═══════════════════════════════════════════════════════════════════
class DifficultyScreen:
    INFO={
        "EASY":  ("2 enemies  |  2 keys","Slow AI  -  No ML","",GREEN),
        "NORMAL":("3 enemies  |  3 keys","Medium  -  ML activates","",YELLOW),
        "HARD":  ("4 enemies  |  4 keys","Fast AI  -  ML active","",ORANGE),
        "INSANE":("5 enemies  |  5 keys","Max speed  -  Full ML","",RED),
    }
    def __init__(self,screen): self.screen=screen; self._t=0.0
    def run(self):
        clock=pygame.time.Clock()
        diffs=list(self.INFO.keys())
        btns={d:pygame.Rect(SCREEN_WIDTH//2-210,180+i*88,420,70) for i,d in enumerate(diffs)}
        back=pygame.Rect(16,SCREEN_HEIGHT-52,110,36)
        while True:
            self._t+=0.02; mx,my=pygame.mouse.get_pos()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
                if ev.type==pygame.KEYDOWN and ev.key==pygame.K_ESCAPE: return None
                if ev.type==pygame.MOUSEBUTTONDOWN:
                    if back.collidepoint(mx,my): return None
                    for d,r in btns.items():
                        if r.collidepoint(mx,my): return d
            self._draw(btns,back,mx,my); clock.tick(FPS)

    def _draw(self,btns,back,mx,my):
        self.screen.fill(BG)
        t=font(30).render("SELECT DIFFICULTY",True,ACCENT)
        self.screen.blit(t,(SCREEN_WIDTH//2-t.get_width()//2,52))
        pygame.draw.line(self.screen,(40,50,80),(SCREEN_WIDTH//2-240,100),(SCREEN_WIDTH//2+240,100),1)
        for d,(d1,d2,_,c) in self.INFO.items():
            r=btns[d]; hov=r.collidepoint(mx,my)
            bg_col=(32,42,64) if hov else (14,18,34)
            s=pygame.Surface((r.w,r.h),pygame.SRCALPHA)
            s.fill((*bg_col,230))
            bc=(*c,220) if hov else (50,62,96,160)
            pygame.draw.rect(s,bc,(0,0,r.w,r.h),2,border_radius=8)
            self.screen.blit(s,(r.x,r.y))
            pygame.draw.rect(self.screen,c,(r.x+4,r.y+8,4,r.h-16),border_radius=2)
            dn=font(20).render(d,True,c if hov else LIGHT_GRAY)
            da=font(12).render(d1,True,WHITE if hov else GRAY)
            db=font(11).render(d2,True,LIGHT_GRAY if hov else (75,80,110))
            self.screen.blit(dn,(r.x+16,r.y+10))
            self.screen.blit(da,(r.x+16,r.y+34))
            self.screen.blit(db,(r.x+16,r.y+50))
        button(self.screen,"BACK",back,back.collidepoint(mx,my),LIGHT_GRAY,13)
        pygame.display.flip()

# ═══════════════════════════════════════════════════════════════════
#  Pause Screen
# ═══════════════════════════════════════════════════════════════════
class PauseScreen:
    def __init__(self,screen): self.screen=screen
    def run(self,snap):
        clock=pygame.time.Clock()
        res=pygame.Rect(SCREEN_WIDTH//2-140,SCREEN_HEIGHT//2-50,280,50)
        men=pygame.Rect(SCREEN_WIDTH//2-140,SCREEN_HEIGHT//2+16,280,50)
        while True:
            mx,my=pygame.mouse.get_pos()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
                if ev.type==pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE,pygame.K_p): return "resume"
                if ev.type==pygame.MOUSEBUTTONDOWN:
                    if res.collidepoint(mx,my): return "resume"
                    if men.collidepoint(mx,my): return "menu"
            self.screen.blit(snap,(0,0))
            ov=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT),pygame.SRCALPHA)
            ov.fill((0,0,0,165)); self.screen.blit(ov,(0,0))
            panel(self.screen,SCREEN_WIDTH//2-200,SCREEN_HEIGHT//2-110,400,230,alpha=245)
            tl=font(34).render("PAUSED",True,ACCENT)
            self.screen.blit(tl,(SCREEN_WIDTH//2-tl.get_width()//2,SCREEN_HEIGHT//2-100))
            pygame.draw.line(self.screen,(40,52,80),
                (SCREEN_WIDTH//2-160,SCREEN_HEIGHT//2-52),(SCREEN_WIDTH//2+160,SCREEN_HEIGHT//2-52),1)
            button(self.screen,"RESUME",res,res.collidepoint(mx,my),GREEN,18)
            button(self.screen,"MAIN MENU",men,men.collidepoint(mx,my),RED,18)
            pygame.display.flip(); clock.tick(FPS)

# ═══════════════════════════════════════════════════════════════════
#  Game Session
# ═══════════════════════════════════════════════════════════════════
class GameSession:
    MAX_LEVEL=3
    def __init__(self,screen,difficulty):
        self.screen=screen; self.difficulty=difficulty
        self.cfg=DIFFICULTY[difficulty]
        self.level=1; self.total_score=0
        self.minimap=Minimap(); self.alerts=Alerts()
        self._pause=PauseScreen(screen)
        self._prev_states={}
        self._load_level()

    def _load_level(self):
        self.game_map=GameMap(self.level)
        self.predictor=MovementPredictor()
        self._ml_timer=ML_RETRAIN_EVERY
        cfg=self.cfg; floors=self.game_map.floor_tiles[:]
        used=[]
        # Player
        opts=[t for t in floors if t[0]<5 and t[1]<4]
        pt=random.choice(opts) if opts else floors[0]
        self.player=Player(*pt); used.append(pt)
        # Exit
        opts=[t for t in floors if t[0]>COLS-7 and t[1]>ROWS-5]
        et=random.choice(opts) if opts else floors[-1]
        self.exit_obj=ExitPortal(*et); used.append(et)
        # Keys
        kn=cfg["keys"]
        kt=random.sample([t for t in floors if t not in used],kn)
        self.keys=[Key(*t) for t in kt]; used+=kt
        # Powerups
        pun=1+(1 if self.difficulty in ("HARD","INSANE") else 0)
        pu_t=random.sample([t for t in floors if t not in used],pun)
        self.powerups=[Powerup(*t) for t in pu_t]; used+=pu_t
        # Enemies — each gets an index for its number label
        en=cfg["enemies"]
        e_pool=[t for t in floors if t not in used and
                abs(t[0]-pt[0])+abs(t[1]-pt[1])>9]
        e_tiles=random.sample(e_pool,min(en,len(e_pool)))
        self.enemies=[Enemy(*et2,idx=i,patrol_spd=cfg["patrol"],
                            chase_spd=cfg["chase"],damage=cfg["damage"],
                            detect_range=int(ENEMY_DETECT_RANGE*cfg["detect"]))
                      for i,et2 in enumerate(e_tiles)]
        self._prev_states={id(e):e.state for e in self.enemies}
        self.floats=[]; self.state="playing"
        self._result_timer=0; self._level_flash=100
        self._frame=0; self._exit_alerted=False
        self.alerts=Alerts()

    def run(self):
        clock=pygame.time.Clock()
        while True:
            r=self._handle_events()
            if r: return r
            self._update()
            self._draw()
            clock.tick(FPS)

    def _handle_events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: return "menu"
                if ev.key==pygame.K_p and self.state=="playing":
                    snap=self.screen.copy()
                    if self._pause.run(snap)=="menu": return "menu"
                if ev.key==pygame.K_r and self.state!="playing":
                    self.level=1; self.total_score=0; self._load_level()
        return None

    def _update(self):
        self._frame+=1
        if self.state!="playing":
            if self.state in ("next_level","won","dead"):
                self._result_timer-=1
                if self._result_timer<=0 and self.state=="next_level":
                    self.level+=1; self._load_level()
            return

        p=self.player; p.update(self.game_map)
        if not p.alive:
            self.state="dead"; self._result_timer=999
            self.alerts.push("YOU DIED !",RED); return

        for k in self.keys:
            k.update()
            if not k.picked and math.hypot(p.x-k.x,p.y-k.y)<TILE_SIZE*0.65:
                k.picked=True; p.keys+=1; pts=150; self.total_score+=pts
                self.floats.append(FloatText(k.x,k.y-10,f"+{pts} KEY",YELLOW))
                self.alerts.push(f"Key {p.keys}/{self.cfg['keys']} collected!",YELLOW)

        for pu in self.powerups:
            pu.update()
            if not pu.collected and math.hypot(p.x-pu.x,p.y-pu.y)<TILE_SIZE*0.65:
                pu.collected=True
                if pu.kind=="speed":
                    p.speed_boost=POWERUP_DURATION
                    self.floats.append(FloatText(pu.x,pu.y-10,"SPEED!",ACCENT))
                    self.alerts.push("Speed Boost activated!",ACCENT)
                elif pu.kind=="shield":
                    p.shield=POWERUP_DURATION
                    self.floats.append(FloatText(pu.x,pu.y-10,"SHIELD!",CYAN))
                    self.alerts.push("Shield activated!",CYAN)
                elif pu.kind=="health":
                    p.heal(35)
                    self.floats.append(FloatText(pu.x,pu.y-10,"+35 HP",GREEN))
                    self.alerts.push("+35 HP restored",GREEN)

        kn=self.cfg["keys"]
        self.exit_obj.open=(p.keys>=kn); self.exit_obj.update()
        if p.keys>=kn and not self._exit_alerted:
            self._exit_alerted=True
            self.alerts.push("EXIT UNLOCKED  -  Reach the portal!",CYAN)
        if self.exit_obj.open:
            if math.hypot(p.x-self.exit_obj.x,p.y-self.exit_obj.y)<TILE_SIZE*0.75:
                bonus=500+max(0,(800-self._frame))
                self.total_score+=bonus
                self.floats.append(FloatText(SCREEN_WIDTH//2,MAZE_OFFSET_Y+60,
                                             f"LEVEL CLEAR  +{bonus}",CYAN))
                self.state="won" if self.level>=self.MAX_LEVEL else "next_level"
                self._result_timer=200; return

        self._ml_timer-=1
        if self._ml_timer<=0:
            was=self.predictor.trained
            self.predictor.train(p.move_history)
            self._ml_timer=ML_RETRAIN_EVERY
            if not was and self.predictor.trained:
                self.alerts.push("ML ONLINE - Enemies now predict!",PURPLE)

        for e in self.enemies:
            prev=self._prev_states.get(id(e),"PATROL")
            e.update(p,self.game_map,self.predictor)
            cur=e.state; idx=e.idx+1
            if prev!=cur:
                if cur=="CHASE" and prev in ("PATROL","DETECT"):
                    self.alerts.push(f"E{idx} is CHASING you!",RED)
                elif cur=="PREDICT":
                    self.alerts.push(f"E{idx} predicting your path!",PURPLE)
                elif cur in ("PATROL","DETECT") and prev in ("CHASE","PREDICT"):
                    self.alerts.push(f"E{idx} lost you.",GRAY)
            self._prev_states[id(e)]=cur

        if self._frame%90==0: self.total_score+=5
        for f in self.floats: f.update()
        self.floats=[f for f in self.floats if f.life>0]
        self.alerts.update()
        if self._level_flash>0: self._level_flash-=1

    def _draw(self):
        self.game_map.draw(self.screen)
        for k  in self.keys:    k.draw(self.screen)
        for pu in self.powerups: pu.draw(self.screen)
        self.exit_obj.draw(self.screen)
        for e in self.enemies:
            e.draw(self.screen)
            e.draw_state_tag(self.screen,font(11))
        self.player.draw(self.screen)
        for f in self.floats: f.draw(self.screen)
        self.alerts.draw(self.screen)

        draw_header(self.screen,self.player,self.cfg["keys"],
                    self.level,self.MAX_LEVEL,self.difficulty,self.total_score)
        draw_footer(self.screen,self.predictor,self.player,self.enemies)
        self.minimap.draw(self.screen,self.game_map,self.player,
                          self.enemies,self.keys,self.exit_obj)

        # Level flash (in maze area)
        if self._level_flash>0:
            a=min(255,self._level_flash*4)
            bt=font(36).render(f"LEVEL  {self.level}",True,ACCENT)
            bt.set_alpha(a)
            self.screen.blit(bt,(SCREEN_WIDTH//2-bt.get_width()//2,
                                  MAZE_OFFSET_Y+MAZE_H//2-20))

        # Overlay
        if   self.state=="dead":
            self._overlay("GAME OVER",RED,
                          f"Score: {self.total_score}     R = Retry   ESC = Menu")
        elif self.state=="won":
            self._overlay("YOU ESCAPED !",CYAN,
                          f"Final Score: {self.total_score}     R = Play Again")
        elif self.state=="next_level":
            self._overlay(f"LEVEL {self.level} CLEAR",GREEN,
                          f"Loading Level {self.level+1} ...")
        pygame.display.flip()

    def _overlay(self,title,col,sub):
        ov=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT),pygame.SRCALPHA)
        ov.fill((0,0,0,170)); self.screen.blit(ov,(0,0))
        panel(self.screen,SCREEN_WIDTH//2-300,SCREEN_HEIGHT//2-70,600,140,alpha=245)
        t=font(40).render(title,True,col)
        s=font(16).render(sub,True,WHITE)
        self.screen.blit(t,(SCREEN_WIDTH//2-t.get_width()//2,SCREEN_HEIGHT//2-58))
        self.screen.blit(s,(SCREEN_WIDTH//2-s.get_width()//2,SCREEN_HEIGHT//2+12))

# ═══════════════════════════════════════════════════════════════════
#  App
# ═══════════════════════════════════════════════════════════════════
class App:
    def __init__(self):
        self.screen=pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        ic=pygame.Surface((32,32)); ic.fill(ACCENT)
        pygame.display.set_icon(ic)
    def run(self):
        menu=MenuScreen(self.screen)
        diff=DifficultyScreen(self.screen)
        while True:
            menu.run()
            d=diff.run()
            if d: GameSession(self.screen,d).run()

if __name__=="__main__":
    App().run()