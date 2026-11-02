"""
SKY RAIDER - pygame 종스크롤 슈팅 게임

조작법
  방향키 / WASD : 이동
  Z / J        : 대공 샷 (공중 적 공격)
  X / K        : 대지 폭탄 (조준점 위치의 지상 목표 공격)
  P            : 일시정지
  Enter        : 시작 / 재시작
  Esc          : 종료

파워업
  P 캡슐을 먹을 때마다 샷이 2 -> 4 -> 8 -> 16발로 강화된다.
  격추되면 한 단계 내려간다.
"""
import math
import os
import random
import sys
from array import array

import pygame

WIDTH, HEIGHT = 480, 720
FPS = 60
TILE = 40
SCROLL_SPEED = 1.2
SIGHT_DIST = 150          # 기체 앞쪽 조준점까지의 거리
BOMB_FLIGHT = 26          # 폭탄이 조준점에 닿기까지 걸리는 프레임
BLAST_RADIUS = 30

HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shooting_highscore.txt")

# 색상
WATER = (40, 90, 170)
WATER_LIGHT = (60, 115, 195)
SAND = (205, 190, 130)
GRASS = [(70, 130, 60), (78, 140, 66), (64, 122, 56)]
TREE = (40, 95, 45)
TREE_DARK = (30, 75, 35)
ROAD = (110, 110, 105)
BRIDGE = (130, 95, 60)
WHITE = (255, 255, 255)
RED = (235, 60, 60)
YELLOW = (255, 220, 80)
ORANGE = (255, 140, 40)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def aim(sx, sy, tx, ty, speed):
    ang = math.atan2(ty - sy, tx - sx)
    return math.cos(ang) * speed, math.sin(ang) * speed


# ---------------------------------------------------------------- 음향 ----
class SoundFX:
    """효과음을 파일 없이 코드로 합성한다. 오디오 장치가 없으면 소리 없이 동작."""

    def __init__(self):
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(16)
        except pygame.error:
            return

        self.sounds = {
            "shot": self.make(self.tone(0.06, 1300, 700, "square", 0.12)),
            "hit": self.make(self.tone(0.03, 320, 220, "square", 0.10)),
            "bomb": self.make(self.tone(0.28, 1000, 350, "sine", 0.22, decay=False)),
            "blast": self.make(self.tone(0.35, 160, 60, "square", 0.40, noise=0.85)),
            "explode": self.make(self.tone(0.40, 220, 80, "square", 0.35, noise=0.70)),
            "big": self.make(self.tone(1.20, 120, 35, "saw", 0.55, noise=0.80)),
            "death": self.make(self.tone(0.90, 700, 50, "saw", 0.45, noise=0.45)),
            "power": self.make(sum((self.tone(0.07, f, f, "square", 0.22, decay=False)
                                    for f in (523, 659, 784, 1047)), [])),
            "bonus": self.make(sum((self.tone(0.06, f, f, "sine", 0.25, decay=False)
                                    for f in (1047, 1319)), [])),
            "extend": self.make(sum((self.tone(0.09, f, f, "square", 0.22, decay=False)
                                     for f in (784, 988, 1175, 1568, 1568)), [])),
        }

    def tone(self, dur, f0, f1, wave, vol, noise=0.0, decay=True):
        """f0 -> f1 로 주파수가 변하는 음 하나를 샘플 리스트로 만든다."""
        n = int(self.rate * dur)
        samples = []
        phase = 0.0
        for i in range(n):
            t = i / n
            phase += (f0 + (f1 - f0) * t) / self.rate
            p = phase % 1.0
            if wave == "square":
                s = 1.0 if p < 0.5 else -1.0
            elif wave == "saw":
                s = 2.0 * p - 1.0
            else:
                s = math.sin(p * math.tau)
            if noise:
                s = s * (1 - noise) + random.uniform(-1, 1) * noise
            env = (1 - t) ** 2 if decay else min(1.0, (1 - t) * 8)
            samples.append(int(s * env * vol * 32767))
        return samples

    def make(self, samples):
        buf = array("h")
        for v in samples:
            buf.extend([v] * self.channels)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        snd = self.sounds.get(name)
        if snd:
            snd.play()


# ---------------------------------------------------------------- 지형 ----
class Terrain:
    """타일 단위로 한 줄씩 생성되며 아래로 흐르는 지형 (강, 숲, 도로)."""

    def __init__(self):
        self.cols = WIDTH // TILE
        self.river_x = random.uniform(3, self.cols - 3)
        self.river_w = 2.0
        self.road_cooldown = 0
        count = HEIGHT // TILE + 2
        self.rows = []   # (surface, river_x, river_w), 0번이 화면 맨 위
        for _ in range(count):
            self.rows.append(self._make_row())
        self.offset = 0.0

    def _make_row(self):
        self.river_x = clamp(self.river_x + random.uniform(-0.35, 0.35), 1.5, self.cols - 1.5)
        self.river_w = clamp(self.river_w + random.uniform(-0.2, 0.2), 1.2, 3.2)
        rx, rw = self.river_x, self.river_w

        surf = pygame.Surface((WIDTH, TILE))
        for c in range(self.cols):
            x = c * TILE
            d = abs(c + 0.5 - rx)
            if d < rw / 2:
                pygame.draw.rect(surf, WATER, (x, 0, TILE, TILE))
                if random.random() < 0.3:
                    wx = x + random.randint(4, TILE - 14)
                    wy = random.randint(6, TILE - 6)
                    pygame.draw.line(surf, WATER_LIGHT, (wx, wy), (wx + 10, wy), 2)
            elif d < rw / 2 + 0.5:
                pygame.draw.rect(surf, SAND, (x, 0, TILE, TILE))
            else:
                pygame.draw.rect(surf, random.choice(GRASS), (x, 0, TILE, TILE))
                if random.random() < 0.35:
                    for _ in range(random.randint(1, 3)):
                        tx = x + random.randint(8, TILE - 8)
                        ty = random.randint(8, TILE - 8)
                        r = random.randint(6, 10)
                        pygame.draw.circle(surf, TREE_DARK, (tx + 2, ty + 2), r)
                        pygame.draw.circle(surf, TREE, (tx, ty), r)

        self.road_cooldown -= 1
        if self.road_cooldown <= 0 and random.random() < 0.05:
            self.road_cooldown = 10
            pygame.draw.rect(surf, ROAD, (0, 10, WIDTH, 20))
            for x in range(0, WIDTH, 30):
                pygame.draw.rect(surf, (200, 200, 190), (x, 19, 14, 2))
            bx0 = int((rx - rw / 2) * TILE)
            bx1 = int((rx + rw / 2) * TILE)
            pygame.draw.rect(surf, BRIDGE, (bx0, 8, bx1 - bx0, 24))
            pygame.draw.line(surf, (90, 60, 35), (bx0, 8), (bx1, 8), 2)
            pygame.draw.line(surf, (90, 60, 35), (bx0, 31), (bx1, 31), 2)

        return surf, rx, rw

    def update(self):
        self.offset += SCROLL_SPEED
        while self.offset >= TILE:
            self.offset -= TILE
            self.rows.pop()
            self.rows.insert(0, self._make_row())

    def is_water(self, x, y):
        idx = clamp(math.floor((y - self.offset) / TILE) + 1, 0, len(self.rows) - 1)
        _, rx, rw = self.rows[idx]
        return abs(x / TILE - rx) < rw / 2 + 0.3

    def draw(self, screen):
        for i, (surf, _, _) in enumerate(self.rows):
            screen.blit(surf, (0, (i - 1) * TILE + self.offset))


# ---------------------------------------------------------------- 플레이어 ----
class Player:
    def __init__(self):
        self.x = WIDTH / 2
        self.y = HEIGHT - 110
        self.speed = 4.5
        self.radius = 6           # 피격 판정은 기체보다 작게
        self.shot_cd = 0
        self.invincible = 120
        self.alive = True

    @property
    def sight(self):
        return self.x, self.y - SIGHT_DIST

    def update(self, keys):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.x = clamp(self.x + dx * self.speed, 18, WIDTH - 18)
        self.y = clamp(self.y + dy * self.speed, SIGHT_DIST + 20, HEIGHT - 24)
        if self.shot_cd > 0:
            self.shot_cd -= 1
        if self.invincible > 0:
            self.invincible -= 1

    def draw(self, screen, frame):
        if self.invincible > 0 and (self.invincible // 4) % 2:
            return
        x, y = int(self.x), int(self.y)
        # 엔진 불꽃
        flame = 6 + (frame % 4) * 2
        pygame.draw.polygon(screen, ORANGE, [(x - 4, y + 13), (x + 4, y + 13), (x, y + 13 + flame)])
        pygame.draw.polygon(screen, YELLOW, [(x - 2, y + 13), (x + 2, y + 13), (x, y + 10 + flame)])
        body = [(x, y - 20), (x + 6, y - 5), (x + 18, y + 7), (x + 18, y + 12), (x + 6, y + 8),
                (x + 4, y + 14), (x - 4, y + 14), (x - 6, y + 8), (x - 18, y + 12), (x - 18, y + 7),
                (x - 6, y - 5)]
        pygame.draw.polygon(screen, (215, 222, 235), body)
        pygame.draw.polygon(screen, (80, 90, 115), body, 2)
        pygame.draw.ellipse(screen, (60, 150, 230), (x - 3, y - 10, 6, 12))
        pygame.draw.line(screen, RED, (x - 16, y + 9), (x - 8, y + 6), 2)
        pygame.draw.line(screen, RED, (x + 16, y + 9), (x + 8, y + 6), 2)

    def draw_sight(self, screen, locked):
        sx, sy = map(int, self.sight)
        color = RED if locked else (240, 240, 240)
        size = 12
        for ax, ay in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            cx, cy = sx + ax * size, sy + ay * size
            pygame.draw.line(screen, color, (cx, cy), (cx - ax * 6, cy), 2)
            pygame.draw.line(screen, color, (cx, cy), (cx, cy - ay * 6), 2)
        pygame.draw.circle(screen, color, (sx, sy), 2)


class Shot:
    def __init__(self, x, y, angle=0.0):
        self.x, self.y = x, y
        self.vx = math.sin(angle) * 12
        self.vy = -math.cos(angle) * 12
        self.alive = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.y < -20 or self.x < -20 or self.x > WIDTH + 20:
            self.alive = False

    def draw(self, screen):
        head = (int(self.x), int(self.y))
        tail = (int(self.x - self.vx), int(self.y - self.vy))
        pygame.draw.line(screen, (255, 255, 180), head, tail, 4)
        pygame.draw.line(screen, WHITE, head, tail, 2)


# 샷 발 수별 (전체 확산 각도(도), 발 사이 가로 간격(px))
SHOT_PATTERNS = {2: (0, 12), 4: (10, 8), 8: (36, 5), 16: (80, 3)}
MAX_POWER = 3   # 0:2발, 1:4발, 2:8발, 3:16발


class PowerItem:
    """좌우로 흔들리며 내려오는 파워업 캡슐."""

    def __init__(self, x, y):
        self.base_x = clamp(x, 40, WIDTH - 40)
        self.x, self.y = self.base_x, y
        self.t = 0
        self.alive = True

    def update(self):
        self.t += 1
        self.y += 1.3
        self.x = self.base_x + math.sin(self.t * 0.06) * 20
        if self.y > HEIGHT + 20:
            self.alive = False

    def draw(self, screen, font):
        x, y = int(self.x), int(self.y)
        color = (60, 140, 255) if (self.t // 8) % 2 else (255, 80, 80)
        pygame.draw.ellipse(screen, (20, 20, 40), (x - 15, y - 11, 30, 22))
        pygame.draw.ellipse(screen, color, (x - 13, y - 9, 26, 18))
        pygame.draw.ellipse(screen, WHITE, (x - 13, y - 9, 26, 18), 2)
        img = font.render("P", True, WHITE)
        screen.blit(img, img.get_rect(center=(x, y)))


class Bomb:
    """기체에서 출발해 조준점(지면과 함께 스크롤되는 지점)으로 떨어지는 폭탄."""

    def __init__(self, x, y, tx, ty):
        self.sx, self.sy = x, y
        self.tx, self.ty = tx, ty
        self.t = 0
        self.alive = True

    @property
    def pos(self):
        p = self.t / BOMB_FLIGHT
        return self.sx + (self.tx - self.sx) * p, self.sy + (self.ty - self.sy) * p

    def update(self):
        self.ty += SCROLL_SPEED
        self.t += 1
        if self.t >= BOMB_FLIGHT:
            self.alive = False

    def draw(self, screen):
        x, y = self.pos
        r = max(2, int(6 - 4 * self.t / BOMB_FLIGHT))
        pygame.draw.circle(screen, (40, 40, 40), (int(x), int(y)), r + 1)
        pygame.draw.circle(screen, YELLOW, (int(x), int(y)), r)


class Blast:
    """폭탄이 지면에 닿았을 때의 폭발 효과 (지면과 함께 스크롤)."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 0
        self.alive = True

    def update(self):
        self.y += SCROLL_SPEED
        self.t += 1
        if self.t > 22:
            self.alive = False

    def draw(self, screen):
        p = self.t / 22
        r = int(BLAST_RADIUS * (0.4 + 0.6 * p))
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        alpha = int(220 * (1 - p))
        pygame.draw.circle(surf, (255, 170, 60, alpha), (r + 1, r + 1), r)
        pygame.draw.circle(surf, (255, 240, 180, alpha), (r + 1, r + 1), max(1, r // 2))
        screen.blit(surf, (int(self.x) - r - 1, int(self.y) - r - 1))


class EnemyBullet:
    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.radius = 4
        self.alive = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if not (-20 < self.x < WIDTH + 20 and -20 < self.y < HEIGHT + 20):
            self.alive = False

    def draw(self, screen, frame):
        c = (255, 120, 200) if (frame // 4) % 2 else (255, 230, 255)
        pygame.draw.circle(screen, (120, 0, 60), (int(self.x), int(self.y)), self.radius + 1)
        pygame.draw.circle(screen, c, (int(self.x), int(self.y)), self.radius)


class Particle:
    def __init__(self, x, y, color, speed=4.0, life=30):
        ang = random.uniform(0, math.tau)
        sp = random.uniform(0.5, speed)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(ang) * sp, math.sin(ang) * sp
        self.color = color
        self.life = self.max_life = random.randint(life // 2, life)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1

    def draw(self, screen):
        r = max(1, int(4 * self.life / self.max_life))
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), r)


# ---------------------------------------------------------------- 적 ----
class Enemy:
    ground = False

    def __init__(self, x, y, hp, radius, score):
        self.x, self.y = x, y
        self.hp = hp
        self.radius = radius
        self.score = score
        self.alive = True
        self.t = 0
        self.flash = 0

    def hit(self, game, dmg=1):
        self.hp -= dmg
        self.flash = 4
        if self.hp <= 0 and self.alive:
            self.alive = False
            game.on_enemy_killed(self)

    def update(self, game):
        self.t += 1
        if self.flash:
            self.flash -= 1
        if self.ground:
            self.y += SCROLL_SPEED
        self.move(game)
        if self.y > HEIGHT + 120 or self.y < -160 or self.x < -100 or self.x > WIDTH + 100:
            self.alive = False

    def move(self, game):
        pass

    def can_fire(self, game):
        return 0 < self.y < game.player.y - 60 and game.player.alive

    def tint(self, color):
        return WHITE if self.flash else color


# --- 공중 적 ---
class Dart(Enemy):
    """플레이어 쪽으로 빠르게 돌진하는 소형기."""

    def __init__(self, game):
        super().__init__(random.uniform(30, WIDTH - 30), -30, 1, 13, 100)
        self.vy = 4 + game.level * 0.3
        self.vx = clamp((game.player.x - self.x) / 110, -2.5, 2.5)

    def move(self, game):
        self.x += self.vx
        self.y += self.vy

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        pts = [(x, y + 14), (x + 12, y - 8), (x, y - 2), (x - 12, y - 8)]
        pygame.draw.polygon(screen, self.tint((230, 90, 70)), pts)
        pygame.draw.polygon(screen, (90, 20, 20), pts, 2)


class Weaver(Enemy):
    """좌우로 흔들리며 내려오면서 가끔 탄을 쏜다."""

    def __init__(self, game):
        super().__init__(random.uniform(90, WIDTH - 90), -30, 2, 14, 200)
        self.base_x = self.x
        self.amp = random.uniform(50, 90)
        self.phase = random.uniform(0, math.tau)
        self.fire_cd = random.randint(40, 100)

    def move(self, game):
        self.y += 2.2
        self.x = self.base_x + math.sin(self.t * 0.05 + self.phase) * self.amp
        self.fire_cd -= 1
        if self.fire_cd <= 0 and self.can_fire(game):
            self.fire_cd = max(60, 130 - game.level * 10)
            game.fire_at(self.x, self.y, 3.2 + game.level * 0.2)

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        pygame.draw.circle(screen, self.tint((150, 90, 220)), (x, y), 14)
        pygame.draw.circle(screen, (60, 30, 100), (x, y), 14, 2)
        spin = self.t * 0.2
        for i in range(3):
            a = spin + i * math.tau / 3
            pygame.draw.line(screen, (230, 210, 255), (x, y), (x + math.cos(a) * 12, y + math.sin(a) * 12), 3)
        pygame.draw.circle(screen, (255, 230, 120), (x, y), 4)


class Hunter(Enemy):
    """내려와서 멈춘 뒤 조준탄을 연사하고 위로 빠져나간다."""

    def __init__(self, game):
        super().__init__(random.uniform(50, WIDTH - 50), -40, 5, 20, 500)
        self.stop_y = random.uniform(110, 250)
        self.state = "enter"
        self.fire_cd = 30
        self.hold = 170

    def move(self, game):
        if self.state == "enter":
            self.y += max(0.6, (self.stop_y - self.y) * 0.05)
            if self.y >= self.stop_y - 2:
                self.state = "hold"
        elif self.state == "hold":
            self.x += clamp((game.player.x - self.x) * 0.01, -1, 1)
            self.fire_cd -= 1
            if self.fire_cd <= 0 and self.can_fire(game):
                self.fire_cd = max(28, 50 - game.level * 3)
                spd = 3.5 + game.level * 0.2
                for spread in (-0.2, 0, 0.2):
                    vx, vy = aim(self.x, self.y, game.player.x, game.player.y, spd)
                    c, s = math.cos(spread), math.sin(spread)
                    game.enemy_bullets.append(EnemyBullet(self.x, self.y + 10, vx * c - vy * s, vx * s + vy * c))
            self.hold -= 1
            if self.hold <= 0:
                self.state = "leave"
        else:
            self.y -= 3

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        wing = [(x - 26, y - 6), (x + 26, y - 6), (x + 16, y + 10), (x - 16, y + 10)]
        pygame.draw.polygon(screen, self.tint((90, 100, 120)), wing)
        pygame.draw.polygon(screen, (30, 35, 50), wing, 2)
        pygame.draw.ellipse(screen, self.tint((170, 180, 200)), (x - 10, y - 16, 20, 34))
        pygame.draw.circle(screen, RED, (x, y + 4), 5)


# --- 지상 적 (지형과 함께 스크롤, 폭탄으로만 파괴) ---
class Turret(Enemy):
    ground = True

    def __init__(self, x, y, game):
        super().__init__(x, y, 1, 15, 300)
        self.fire_cd = random.randint(30, 90)
        self.angle = math.pi / 2

    def move(self, game):
        self.angle = math.atan2(game.player.y - self.y, game.player.x - self.x)
        self.fire_cd -= 1
        if self.fire_cd <= 0 and self.can_fire(game):
            self.fire_cd = max(55, 120 - game.level * 8)
            game.fire_at(self.x, self.y, 3 + game.level * 0.2)

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        pygame.draw.rect(screen, (70, 70, 75), (x - 15, y - 15, 30, 30))
        pygame.draw.rect(screen, (40, 40, 45), (x - 15, y - 15, 30, 30), 2)
        pygame.draw.circle(screen, self.tint((150, 150, 140)), (x, y), 10)
        ex = x + math.cos(self.angle) * 16
        ey = y + math.sin(self.angle) * 16
        pygame.draw.line(screen, (30, 30, 30), (x, y), (ex, ey), 5)


class Tank(Enemy):
    ground = True

    def __init__(self, x, y, game):
        super().__init__(x, y, 1, 14, 400)
        self.vx = random.choice((-0.8, 0.8))
        self.fire_cd = random.randint(60, 140)

    def move(self, game):
        nx = self.x + self.vx
        if nx < 20 or nx > WIDTH - 20 or game.terrain.is_water(nx + self.vx * 16, self.y):
            self.vx = -self.vx
        else:
            self.x = nx
        self.fire_cd -= 1
        if self.fire_cd <= 0 and self.can_fire(game):
            self.fire_cd = max(80, 160 - game.level * 10)
            game.fire_at(self.x, self.y, 2.8 + game.level * 0.2)

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        pygame.draw.rect(screen, (40, 40, 30), (x - 14, y - 12, 6, 24))
        pygame.draw.rect(screen, (40, 40, 30), (x + 8, y - 12, 6, 24))
        pygame.draw.rect(screen, self.tint((150, 140, 80)), (x - 9, y - 10, 18, 20))
        pygame.draw.circle(screen, self.tint((120, 110, 60)), (x, y), 7)
        pygame.draw.line(screen, (40, 40, 30), (x, y), (x, y + 14), 4)


class Radar(Enemy):
    """공격하지 않지만 점수가 높은 레이더 기지."""
    ground = True

    def __init__(self, x, y, game):
        super().__init__(x, y, 1, 17, 1000)

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        pygame.draw.circle(screen, (60, 60, 60), (x, y), 18)
        pygame.draw.circle(screen, self.tint((200, 200, 210)), (x, y), 15)
        a = self.t * 0.08
        pygame.draw.line(screen, (40, 160, 80), (x, y), (x + math.cos(a) * 13, y + math.sin(a) * 13), 3)
        pygame.draw.circle(screen, (40, 160, 80), (x, y), 3)


class Fortress(Enemy):
    """주기적으로 나타나는 대형 지상 요새. 중앙 코어에 폭탄 3발이 필요하다."""
    ground = True

    def __init__(self, game):
        super().__init__(WIDTH / 2, -100, 3, 30, 5000)
        self.fire_cd = 90
        for ox, oy in ((-60, -45), (60, -45), (-60, 45), (60, 45)):
            game.enemies.append(Turret(self.x + ox, self.y + oy, game))

    def move(self, game):
        self.fire_cd -= 1
        if self.fire_cd <= 0 and 0 < self.y < HEIGHT - 150:
            self.fire_cd = max(60, 100 - game.level * 5)
            n = 10 + game.level
            base = self.t * 0.03
            for i in range(n):
                a = base + i * math.tau / n
                game.enemy_bullets.append(EnemyBullet(self.x, self.y, math.cos(a) * 2.6, math.sin(a) * 2.6))

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        pts = []
        for i in range(8):
            a = math.pi / 8 + i * math.tau / 8
            pts.append((x + math.cos(a) * 95, y + math.sin(a) * 75))
        pygame.draw.polygon(screen, (95, 95, 105), pts)
        pygame.draw.polygon(screen, (45, 45, 55), pts, 4)
        pygame.draw.circle(screen, (70, 70, 80), (x, y), 44)
        pulse = 180 + int(60 * math.sin(self.t * 0.15))
        pygame.draw.circle(screen, self.tint((pulse, 40, 60)), (x, y), 26)
        pygame.draw.circle(screen, (255, 200, 200), (x, y), 9)


# ---------------------------------------------------------------- 게임 ----
class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("SKY RAIDER")
        self.sfx = SoundFX()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas,arial", 20, bold=True)
        self.item_font = pygame.font.SysFont("consolas,arial", 16, bold=True)
        self.big_font = pygame.font.SysFont("consolas,arial", 52, bold=True)
        self.high = self.load_high()
        self.terrain = Terrain()
        self.state = "title"
        self.paused = False
        self.reset()

    # --- 상태 관리 ---
    def reset(self):
        self.player = Player()
        self.shots, self.bombs, self.blasts = [], [], []
        self.enemies, self.enemy_bullets, self.particles = [], [], []
        self.items = []
        self.power = 0
        self.score = 0
        self.lives = 2              # 남은 예비 기체
        self.frame = 0
        self.next_fortress = FPS * 40
        self.next_extend = 20000
        self.respawn_timer = 0

    @property
    def level(self):
        return 1 + self.frame // (FPS * 30)

    def load_high(self):
        try:
            with open(HIGHSCORE_FILE) as f:
                return int(f.read().strip() or 0)
        except (OSError, ValueError):
            return 0

    def save_high(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                f.write(str(self.high))
        except OSError:
            pass

    # --- 보조 함수 ---
    def fire_at(self, x, y, speed):
        vx, vy = aim(x, y, self.player.x, self.player.y, speed)
        self.enemy_bullets.append(EnemyBullet(x, y, vx, vy))

    def explode(self, x, y, count=20, colors=(ORANGE, YELLOW, RED, WHITE), speed=4.0):
        for _ in range(count):
            self.particles.append(Particle(x, y, random.choice(colors), speed))

    def add_score(self, pts):
        self.score += pts
        if self.score >= self.next_extend:
            self.next_extend += 30000
            self.lives += 1
            self.sfx.play("extend")
        if self.score > self.high:
            self.high = self.score

    def on_enemy_killed(self, enemy):
        self.add_score(enemy.score)
        # 사냥기·레이더·요새는 반드시, 나머지는 낮은 확률로 파워업을 떨어뜨린다
        if isinstance(enemy, (Hunter, Radar, Fortress)) or random.random() < 0.04:
            self.items.append(PowerItem(enemy.x, enemy.y))
        if isinstance(enemy, Fortress):
            self.sfx.play("big")
            self.explode(enemy.x, enemy.y, 120, speed=9)
            # 요새가 무너지면 화면의 적 탄을 모두 지운다
            for b in self.enemy_bullets:
                self.explode(b.x, b.y, 2, colors=((255, 200, 255),), speed=1.5)
            self.enemy_bullets.clear()
        elif enemy.ground:
            self.explode(enemy.x, enemy.y, 25, colors=((90, 80, 70), ORANGE, YELLOW))
        else:
            self.sfx.play("explode")
            self.explode(enemy.x, enemy.y, 22)

    def fire_volley(self):
        p = self.player
        n = 2 ** (self.power + 1)
        spread, gap = SHOT_PATTERNS[n]
        for i in range(n):
            k = i - (n - 1) / 2
            angle = math.radians(spread) * k / (n - 1)
            self.shots.append(Shot(p.x + k * gap, p.y - 12, angle))
        self.sfx.play("shot")

    def collect_item(self):
        if self.power < MAX_POWER:
            self.power += 1
            self.sfx.play("power")
        else:
            self.add_score(1000)
            self.sfx.play("bonus")

    def kill_player(self):
        p = self.player
        p.alive = False
        self.sfx.play("death")
        self.power = max(0, self.power - 1)
        self.explode(p.x, p.y, 60, speed=6)
        self.enemy_bullets.clear()
        self.respawn_timer = 90

    def sight_locked(self):
        sx, sy = self.player.sight
        return any(e.ground and math.hypot(e.x - sx, e.y - sy) < e.radius + 8 for e in self.enemies)

    # --- 적 생성 ---
    def spawn_enemies(self):
        lv = self.level
        boss = any(isinstance(e, Fortress) for e in self.enemies)
        rate = 0.35 if boss else 1.0

        if random.random() < (0.010 + lv * 0.004) * rate:
            r = random.random()
            if r < 0.5:
                self.enemies.append(Dart(self))
            elif r < 0.85:
                self.enemies.append(Weaver(self))
            else:
                self.enemies.append(Hunter(self))
            # 돌진기는 가끔 편대로 등장
            if r < 0.15:
                for _ in range(2):
                    self.enemies.append(Dart(self))

        if random.random() < (0.007 + lv * 0.002) * rate:
            for _ in range(10):
                x = random.uniform(30, WIDTH - 30)
                if not self.terrain.is_water(x, -30):
                    kind = random.choices((Turret, Tank, Radar), (5, 4, 1))[0]
                    self.enemies.append(kind(x, -30, self))
                    break

        if self.frame >= self.next_fortress and not boss:
            self.next_fortress = self.frame + FPS * 50
            self.enemies.append(Fortress(self))

    # --- 갱신 ---
    def update(self):
        keys = pygame.key.get_pressed()
        self.terrain.update()

        if self.state != "playing":
            return

        self.frame += 1
        p = self.player

        if p.alive:
            p.update(keys)
            if (keys[pygame.K_z] or keys[pygame.K_j]) and p.shot_cd == 0:
                p.shot_cd = 7
                self.fire_volley()
            # 폭탄은 화면에 한 발만
            if (keys[pygame.K_x] or keys[pygame.K_k]) and not self.bombs:
                sx, sy = p.sight
                self.bombs.append(Bomb(p.x, p.y - 10, sx, sy))
                self.sfx.play("bomb")
        else:
            self.respawn_timer -= 1
            if self.respawn_timer <= 0:
                if self.lives > 0:
                    self.lives -= 1
                    self.player = Player()
                else:
                    self.state = "gameover"
                    self.save_high()

        self.spawn_enemies()

        for obj in self.shots + self.bombs + self.blasts + self.enemy_bullets + self.particles + self.items:
            obj.update()
        for e in list(self.enemies):
            e.update(self)

        # 폭탄 착탄 -> 지상 적 판정
        for b in self.bombs:
            if not b.alive:
                self.sfx.play("blast")
                self.blasts.append(Blast(b.tx, b.ty))
                self.explode(b.tx, b.ty, 10, colors=(ORANGE, YELLOW), speed=2.5)
                for e in self.enemies:
                    if e.ground and e.alive and math.hypot(e.x - b.tx, e.y - b.ty) < BLAST_RADIUS + e.radius:
                        e.hit(self)

        # 대공 샷 -> 공중 적 판정
        for s in self.shots:
            for e in self.enemies:
                if not e.ground and e.alive and s.alive and math.hypot(e.x - s.x, e.y - s.y) < e.radius + 4:
                    s.alive = False
                    e.hit(self)
                    if e.alive:
                        self.sfx.play("hit")
                    self.particles.append(Particle(s.x, s.y, YELLOW, 2, 10))

        # 파워업 획득
        p = self.player
        if p.alive:
            for it in self.items:
                if math.hypot(it.x - p.x, it.y - p.y) < 26:
                    it.alive = False
                    self.collect_item()
        if p.alive and p.invincible == 0:
            for b in self.enemy_bullets:
                if math.hypot(b.x - p.x, b.y - p.y) < b.radius + p.radius:
                    self.kill_player()
                    break
            else:
                for e in self.enemies:
                    if not e.ground and e.alive and math.hypot(e.x - p.x, e.y - p.y) < e.radius + p.radius:
                        e.hit(self, 99)
                        self.kill_player()
                        break

        self.shots = [o for o in self.shots if o.alive]
        self.bombs = [o for o in self.bombs if o.alive]
        self.blasts = [o for o in self.blasts if o.alive]
        self.enemies = [o for o in self.enemies if o.alive]
        self.enemy_bullets = [o for o in self.enemy_bullets if o.alive]
        self.particles = [o for o in self.particles if o.life > 0]
        self.items = [o for o in self.items if o.alive]

    # --- 그리기 ---
    def text(self, msg, y, font=None, color=WHITE, center=True, x=0):
        font = font or self.font
        img = font.render(msg, True, color)
        shadow = font.render(msg, True, (0, 0, 0))
        rect = img.get_rect()
        if center:
            rect.center = (WIDTH // 2, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(shadow, rect.move(2, 2))
        self.screen.blit(img, rect)
        return rect

    def draw_hud(self):
        self.text(f"SCORE {self.score:>7}", 10, center=False, x=10)
        hi = self.font.render(f"HI {self.high:>7}", True, YELLOW)
        self.screen.blit(hi, (WIDTH - hi.get_width() - 10, 10))
        self.text(f"LV {self.level}", 34, center=False, x=10, color=(180, 220, 255))
        self.text(f"SHOT x{2 ** (self.power + 1)}", 58, center=False, x=10, color=(255, 180, 120))
        for i in range(self.lives):
            x, y = 18 + i * 22, HEIGHT - 18
            pygame.draw.polygon(self.screen, (215, 222, 235),
                                [(x, y - 9), (x + 8, y + 6), (x, y + 3), (x - 8, y + 6)])

    def draw(self, frame):
        s = self.screen
        self.terrain.draw(s)

        if self.state in ("playing", "gameover"):
            for e in self.enemies:
                if e.ground:
                    e.draw(s)
            for b in self.blasts:
                b.draw(s)
            for b in self.bombs:
                b.draw(s)
            for e in self.enemies:
                if not e.ground:
                    e.draw(s)
            for sh in self.shots:
                sh.draw(s)
            for it in self.items:
                it.draw(s, self.item_font)
            if self.player.alive:
                self.player.draw(s, frame)
                self.player.draw_sight(s, self.sight_locked())
            for p in self.particles:
                p.draw(s)
            for b in self.enemy_bullets:
                b.draw(s, frame)
            self.draw_hud()

        if self.state == "title":
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 20, 140))
            s.blit(shade, (0, 0))
            self.text("SKY RAIDER", 220, self.big_font, YELLOW)
            lines = ["ARROWS / WASD : MOVE",
                     "Z / J : AIR SHOT",
                     "X / K : GROUND BOMB",
                     "P : PAUSE    ESC : QUIT"]
            for i, line in enumerate(lines):
                self.text(line, 320 + i * 32)
            if (frame // 30) % 2:
                self.text("PRESS ENTER TO START", 500, color=(255, 200, 120))
            self.text(f"HIGH SCORE {self.high}", 560, color=YELLOW)
        elif self.state == "gameover":
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((20, 0, 0, 150))
            s.blit(shade, (0, 0))
            self.text("GAME OVER", 290, self.big_font, RED)
            self.text(f"SCORE {self.score}", 360)
            if (frame // 30) % 2:
                self.text("PRESS ENTER TO RETRY", 430, color=(255, 200, 120))
        if self.paused:
            self.text("PAUSED", HEIGHT // 2, self.big_font)

        pygame.display.flip()

    # --- 메인 루프 ---
    def run(self):
        frame = 0
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.quit()
                    elif event.key == pygame.K_RETURN and self.state in ("title", "gameover"):
                        self.reset()
                        self.state = "playing"
                    elif event.key == pygame.K_p and self.state == "playing":
                        self.paused = not self.paused

            if not self.paused:
                self.update()
            self.draw(frame)
            frame += 1
            self.clock.tick(FPS)

    def quit(self):
        self.save_high()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
