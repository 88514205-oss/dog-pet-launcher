"""神吞娘 · 桌宠模块（二创像素娘化形象）。

顺便当作"怎么写一个自己的模块"的参考实现：
只依赖 host.world / host.particles / host.play，不到 120 行。
"""

import math
import os
import random

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap, QRegion

from dogpet import assets
from dogpet.vec import V

FRAMES = 10
TICK_PER_FRAME = 6.0        # 与 Terraria 一致的换帧节奏（每 6 tick 一帧）
HOVER = 46.0 * 2.2          # 在鼠标上方悬停的高度


def create(host):
    return DogchanPet(host)


class DogchanPet:
    def __init__(self, host):
        self.host = host
        self.frames = []
        for i in range(FRAMES):
            p = assets.path("dogchan", f"dogchan_a{i:02d}.png")
            if os.path.isfile(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    self.frames.append(pm)
        self.scale = float(host.settings.get("dogchan_scale", 2.2))
        self.pos = V(host.world.origin_x + host.world.W * 0.5,
                     host.world.ground_y - 300)
        self.vel = V()
        self.frame = 0
        self.counter = 0.0
        self.bob = random.uniform(0, 6.28)

    # ---- 尺寸 -----------------------------------------------------------
    def _size(self):
        if not self.frames:
            return (40.0, 40.0)
        return (self.frames[0].width() * self.scale,
                self.frames[0].height() * self.scale)

    def _center(self):
        w, h = self._size()
        return V(self.pos.x + w * 0.5, self.pos.y + h * 0.5)

    # ---- 每 tick ---------------------------------------------------------
    def update(self, ticks):
        host = self.host
        w = host.world
        self.bob += 0.045 * ticks
        want = host.engine.target.pos
        # 飘在目标上方，带一点上下浮动
        tx = want.x
        ty = want.y - HOVER + math.sin(self.bob) * 14.0 * self.scale
        dx = tx - self.pos.x
        dy = ty - self.pos.y
        k = 0.055 * ticks
        self.vel.x += (dx * 0.9 - self.vel.x) * k
        self.vel.y += (dy * 0.9 - self.vel.y) * k
        self.pos.x += self.vel.x * ticks
        self.pos.y += self.vel.y * ticks
        sw, sh = self._size()
        self.pos.x = max(w.origin_x - 40, min(self.pos.x, w.origin_x + w.W - sw + 40))
        self.pos.y = max(w.origin_y - 40, min(self.pos.y, w.ground_y - sh + 40))

        self.counter += ticks
        while self.counter >= TICK_PER_FRAME:
            self.counter -= TICK_PER_FRAME
            self.frame = (self.frame + 1) % max(len(self.frames), 1)

        cx, cy = self._center().x, self._center().y
        if abs(self.vel.x) + abs(self.vel.y) > 3.0 and random.random() < 0.35:
            host.particles.trail_dust(cx, cy, -self.vel.x * 0.3, -self.vel.y * 0.3, 1)

    # ---- 脏区 / 命中 ------------------------------------------------------
    def bounds(self):
        w, h = self._size()
        pad = 120
        return QRegion(QRect(int(self.pos.x - pad), int(self.pos.y - pad),
                             int(w + pad * 2), int(h + pad * 2)))

    def render_box(self):
        w, h = self._size()
        return (self.pos.x - 12, self.pos.y - 12, w + 24, h + 24)

    def pet_position(self):
        return V(self.pos.x, self.pos.y)

    def place(self, gx, gy):
        self.pos = V(gx, gy)
        self.vel = V()

    def recenter(self):
        w = self.host.world
        self.pos = V(w.origin_x + w.W * 0.5, w.origin_y + w.H * 0.5)
        self.vel = V()

    # ---- 绘制 ------------------------------------------------------------
    def draw(self, p, host):
        if not self.frames:
            return
        pm = self.frames[min(self.frame, len(self.frames) - 1)]
        w, h = self._size()
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawPixmap(QRectF(self.pos.x, self.pos.y, w, h), pm,
                     QRectF(0, 0, pm.width(), pm.height()))
