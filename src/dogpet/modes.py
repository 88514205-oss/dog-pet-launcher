"""四种行为模式：跟随 / 攻击鼠标 / 寻空游动 / 吞噬。"""

import math
import random

from PySide6.QtGui import QCursor

from . import config as C
from .vec import V


class Target:
    """被宠物追踪的目标，等价于游戏里的「玩家」。"""

    __slots__ = ("pos", "last_pos", "vel", "dir_x", "life_ratio", "moving")

    def __init__(self):
        self.pos = V()
        self.last_pos = V()
        self.vel = V()
        self.dir_x = 1.0
        self.life_ratio = 1.0
        self.moving = False

    def sync(self):
        self.last_pos = self.pos.copy()
        self.vel = V()
        self.moving = False

    def move_to(self, p):
        self.vel = p - self.pos
        if abs(self.vel.x) > 0.2:
            self.dir_x = 1.0 if self.vel.x > 0 else -1.0
        self.moving = self.vel.length() > 0.5
        self.pos = p.copy()


class OrbitPoint:
    """寻空模式里的巡游航点。"""

    def __init__(self, world):
        self.world = world
        self.p = V()
        self.timer = 0.0
        self.pick()

    def pick(self):
        w = self.world
        self.p = V(w.origin_x + random.uniform(0.12, 0.88) * w.W,
                   w.origin_y + random.uniform(0.06, 0.62) * w.H)
        self.timer = random.uniform(120.0, 260.0)

    def update(self, ticks):
        self.timer -= ticks
        if self.timer <= 0:
            self.pick()


class Star:
    """吞噬模式里的星体光点。"""

    __slots__ = ("pos", "vel", "life", "radius", "hue", "eaten")

    def __init__(self, x, y, radius=9.0):
        self.pos = V(x, y)
        ang = random.uniform(0, math.tau)
        sp = random.uniform(0.4, 1.5)
        self.vel = V(math.cos(ang) * sp, math.sin(ang) * sp)
        self.life = random.uniform(420.0, 900.0)
        self.radius = radius
        self.hue = random.randint(0, 2)
        self.eaten = False

    def update(self, ticks, world):
        self.pos = self.pos + self.vel * ticks
        self.life -= ticks
        pad = 20.0
        if self.pos.x < world.origin_x + pad:
            self.pos.x = world.origin_x + pad
            self.vel.x = abs(self.vel.x)
        elif self.pos.x > world.origin_x + world.W - pad:
            self.pos.x = world.origin_x + world.W - pad
            self.vel.x = -abs(self.vel.x)
        if self.pos.y < world.origin_y + pad:
            self.pos.y = world.origin_y + pad
            self.vel.y = abs(self.vel.y)
        elif self.pos.y > world.ground_y - pad:
            self.pos.y = world.ground_y - pad
            self.vel.y = -abs(self.vel.y)


class ModeEngine:
    def __init__(self, world, mode=None, target_source="mouse"):
        self.world = world
        self.mode = mode or C.MODE_FOLLOW
        self.target_source = target_source      # "mouse" 追鼠标 / "heart" 追决心
        self.target = Target()
        self.target.pos = world.cursor()
        self.target.sync()
        self.smooth = V(self.target.pos.x, self.target.pos.y)
        self.orbit = OrbitPoint(world)
        self.stars = []
        self.star_timer = 60.0
        self.eaten = 0
        self.devour_flash = 0.0

    def set_mode(self, mode):
        self.mode = mode
        if mode == C.MODE_DEVOUR:
            self.stars.clear()
            self.star_timer = 10.0

    def set_target_source(self, src):
        """鼠标 / 决心：决定宠物去追谁。"""
        self.target_source = src

    def update(self, ticks, heart=None):
        if self.target_source == "heart" and heart is not None:
            # 追"决心"：目标就是那颗红心
            self.target.move_to(heart.pos)
            self.target.life_ratio = 1.0
            return
        if self.mode == C.MODE_SKY:
            self._update_sky(ticks)
        elif self.mode == C.MODE_DEVOUR:
            self._update_devour(ticks)
        else:
            self._update_cursor(ticks)
        self.target.life_ratio = 1.0

    def _update_cursor(self, ticks):
        cur = self.world.cursor()
        if self.mode == C.MODE_HUNT:
            self.smooth = V(cur.x, cur.y)
            self.target.move_to(cur)
            return
        k = 0.10 * ticks
        self.smooth.x += (cur.x - self.smooth.x) * k
        self.smooth.y += (cur.y - self.smooth.y) * k
        self.target.move_to(self.smooth)

    def _update_sky(self, ticks):
        self.orbit.update(ticks)
        k = 0.045 * ticks
        self.smooth.x += (self.orbit.p.x - self.smooth.x) * k
        self.smooth.y += (self.orbit.p.y - self.smooth.y) * k
        wob = math.sin(self.orbit.timer * 0.05) * 26.0
        self.target.move_to(V(self.smooth.x, self.smooth.y + wob))

    def _update_devour(self, ticks):
        w = self.world
        self.devour_flash = max(0.0, self.devour_flash - ticks * 0.02)
        self.star_timer -= ticks
        if self.star_timer <= 0 and len(self.stars) < 14:
            self.star_timer = random.uniform(50.0, 130.0)
            x = random.uniform(w.origin_x + w.W * 0.08, w.origin_x + w.W * 0.92)
            y = random.uniform(w.origin_y + w.H * 0.08, w.ground_y - w.H * 0.12)
            self.stars.append(Star(x, y, random.uniform(6.0, 13.0)))
        alive = []
        for st in self.stars:
            st.update(ticks, w)
            if not st.eaten and st.life > 0:
                alive.append(st)
        self.stars = alive

        if self.stars:
            nearest = min(self.stars, key=lambda s: s.pos.distance_sq(self.target.pos))
            self.target.move_to(nearest.pos)
        else:
            self._update_sky(ticks)

    def consume(self, pos, radius):
        if self.mode != C.MODE_DEVOUR:
            return 0
        got = 0
        for st in self.stars:
            if not st.eaten and st.pos.distance(pos) < radius + st.radius:
                st.eaten = True
                got += 1
        if got:
            self.eaten += got
            self.devour_flash = min(1.6, self.devour_flash + 0.5 * got)
        return got

    def eat_burst_count(self):
        return self.eaten
