# ─── player.py  v3.2 ─────────────────────────────────────────────
import pygame, math, random
from settings import *

class Player:
    def __init__(self, col, row):
        self.col = col; self.row = row
        self.x = float(col*TILE_SIZE + TILE_SIZE//2)
        self.y = float(MAZE_OFFSET_Y + row*TILE_SIZE + TILE_SIZE//2)
        self.health = PLAYER_HEALTH; self.max_health = PLAYER_HEALTH
        self.keys = 0; self.alive = True
        self.move_history = []
        
        # FIX: Track last known tile to prevent frame-flooding the ML history
        self.last_tile = (col, row)
        
        self._inv = 0; self._half = PLAYER_SIZE//2
        self._trail = []; self._bob = 0.0
        self.speed_boost = 0; self.shield = 0
        self._particles = []

    def current_speed(self):
        return PLAYER_SPEED * (1.6 if self.speed_boost > 0 else 1.0)

    def update(self, game_map):
        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx = -self.current_speed()
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx =  self.current_speed()
        if keys[pygame.K_UP]    or keys[pygame.K_w]: dy = -self.current_speed()
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy =  self.current_speed()
        if dx and dy: dx *= 0.707; dy *= 0.707

        # Actual movement calculations
        px, py = self.x, self.y
        self._move(dx, 0, game_map)
        self._move(0, dy, game_map)

        # FIX: Tile movement history validation logic
        # Frame logging band! Ab data tabhi save hoga jab actual tile position change hogi.
        current_tile = (self.col, self.row)
        if current_tile != self.last_tile:
            # Check direction based on wall collision output values
            # 0: Idle, 1: Up, 2: Down, 3: Left, 4: Right
            d = 0
            if self.row < self.last_tile[1]: d = 1    # Up
            elif self.row > self.last_tile[1]: d = 2  # Down
            elif self.col < self.last_tile[0]: d = 3  # Left
            elif self.col > self.last_tile[0]: d = 4  # Right
            
            if d != 0:
                self.move_history.append(d)
                if len(self.move_history) > 600: 
                    self.move_history.pop(0)
                    
            self.last_tile = current_tile # Update context anchor

        # Graphics, animation and particle effects management
        if abs(self.x-px)>0.5 or abs(self.y-py)>0.5:
            self._trail.append([self.x, self.y, 0])
        self._trail = [[x,y,a+1] for x,y,a in self._trail if a<10]
        self._bob = (self._bob+0.12) % (2*math.pi)
        if self._inv>0: self._inv-=1
        if self.speed_boost>0: self.speed_boost-=1
        if self.shield>0: self.shield-=1
        self._particles = [(x+vx,y+vy,vx,vy,l-1,c)
                           for x,y,vx,vy,l,c in self._particles if l>0]

    def _move(self, dx, dy, gm):
        nx, ny = self.x+dx, self.y+dy
        h = self._half-2
        for cx,cy in [(nx-h,ny-h),(nx+h,ny-h),(nx-h,ny+h),(nx+h,ny+h)]:
            col = int(cx // TILE_SIZE)
            row = int((cy - MAZE_OFFSET_Y) // TILE_SIZE)
            if gm.is_wall(col, row): return
        self.x, self.y = nx, ny
        self.col = int(self.x // TILE_SIZE)
        self.row = int((self.y - MAZE_OFFSET_Y) // TILE_SIZE)

    def take_damage(self, amount):
        if self._inv>0 or self.shield>0: return
        self.health -= amount; self._inv = 50
        for _ in range(8):
            vx=random.uniform(-2,2); vy=random.uniform(-2,2)
            self._particles.append((self.x,self.y,vx,vy,20,RED))
        if self.health<=0: self.health=0; self.alive=False

    def heal(self, amount):
        self.health = min(self.max_health, self.health+amount)

    @property
    def rect(self):
        return pygame.Rect(self.x-self._half, self.y-self._half,
                           PLAYER_SIZE, PLAYER_SIZE)

    def draw(self, surf):
        # Trail rendering
        for x,y,age in self._trail:
            r = max(2, self._half-age*2)
            s = pygame.Surface((r*2,r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*GREEN, max(0,150-age*15)), (r,r), r)
            surf.blit(s, (int(x)-r, int(y)-r))

        if self._inv>0 and (self._inv//5)%2==0: return

        bx=int(self.x); by=int(self.y+math.sin(self._bob)*1.5)
        h=self._half

        # Shield ring
        if self.shield>0:
            pygame.draw.circle(surf,(*CYAN,120),(bx,by),h+8,3)

        # Glow
        g=pygame.Surface((h*4,h*4),pygame.SRCALPHA)
        bc=ACCENT if self.speed_boost>0 else GREEN
        pygame.draw.circle(g,(*bc,38),(h*2,h*2),h*2)
        surf.blit(g,(bx-h*2,by-h*2))

        # Body
        pygame.draw.circle(surf,DARK_GREEN,(bx,by),h+2)
        pygame.draw.circle(surf,bc,(bx,by),h)
        pygame.draw.circle(surf,(255,255,255,70),(bx-h//4,by-h//4),h//3)

        # Eyes
        for ex_off in [-5,5]:
            ex,ey=bx+ex_off,by-4
            pygame.draw.circle(surf,WHITE,(ex,ey),4)
            pygame.draw.circle(surf,(20,20,20),(ex,ey),2)
            pygame.draw.circle(surf,WHITE,(ex+1,ey-1),1)

        # Particles
        for x,y,vx,vy,l,c in self._particles:
            a=int(255*(l/20))
            s=pygame.Surface((4,4),pygame.SRCALPHA)
            pygame.draw.circle(s,(*c,a),(2,2),2)
            surf.blit(s,(int(x)-2,int(y)-2))