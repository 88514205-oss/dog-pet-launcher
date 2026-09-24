"""粒子、拖尾与屏幕特效层。"""

import math
import os
import random

from PySide6.QtCore import QPointF, Qt, QRect, QRectF
from PySide6.QtGui import (QBrush, QColor, QPainter, QPen, QPixmap,
                           QRadialGradient)

from .vec import V
from .config import (PET_ACCEL as C_PET_ACCEL,
                     PET_FRICTION as C_PET_FRICTION,
                     PET_MAX_SPEED as C_PET_MAX_SPEED,
                     PET_TURN_THRESHOLD as C_PET_TURN_THRESHOLD)

# Terraria DustID：182 用于宠物切换陆地/飞行时爆出的尘
DUST_SWITCH = ((186, 92, 255), (96, 214, 255), (222, 168, 255))
DUST_GLOW = ((120, 240, 255), (188, 120, 255))
DUST_DEVOUR = ((255, 216, 128), (255, 160, 96), (168, 232, 255))

# 决心：16x16，UT 那种饱满的像素心
HEART_PIX = (
    "0001100000110000",
    "0011110001111000",
    "0111111011111100",
    "1111111111111110",
    "1111111111111110",
    "1111111111111110",
    "1111111111111110",
    "1111111111111110",
    "0111111111111100",
    "0111111111111100",
    "0011111111111000",
    "0001111111110000",
    "0000111111100000",
    "0000011111000000",
    "0000001110000000",
    "0000000100000000",
)


class Heart:
    """决心：桌宠的另一种追踪目标。

    移动参数直接照搬 ChibiiPet（Q版神吞）那套：
    加速度、速度上限、转向衰减、摩擦，全都同款，所以惯性和偏移手感一致。
    速度快时留下渐隐拖尾。
    """

    SIZE = 32                # 显示尺寸；实际按素材整数倍放大（16 → 32 即 2x）
    SCALE = 1.6              # 物理尺度系数，和 Q版显示比例类似
    TRAIL_LEN = 12

    def __init__(self, world):
        self.world = world
        self.pos = V(world.origin_x + world.W * 0.5,
                     world.origin_y + world.H * 0.42)
        self.vel = V()
        self.dragging = False
        self.cursor = V(self.pos.x, self.pos.y)
        self.retarget = random.uniform(60.0, 180.0)
        self.trail = [self.pos.copy() for _ in range(self.TRAIL_LEN)]
        self.pulse = 0.0
        # UT 原版红心素材（16x16）；缺素材时退回内置像素字形
        self.pix = None
        self.pix_dmg = None
        try:
            from . import assets as _assets
            for name, attr in (("heart.png", "pix"), ("heart_dmg.png", "pix_dmg")):
                p = _assets.path("ut", name)
                if os.path.isfile(p):
                    pm = QPixmap(p)
                    if not pm.isNull():
                        setattr(self, attr, pm)
        except Exception:
            pass
        self.pix_size = self.pix.width() if self.pix is not None else len(HEART_PIX[0])

    # ---- 移动：与 Q版神吞同款 -------------------------------------------
    def update(self, ticks):
        self.pulse = (self.pulse + 0.05 * ticks) % 1.0
        s = self.SCALE
        accel = C_PET_ACCEL * s * ticks
        max_speed = C_PET_MAX_SPEED * s
        turn = C_PET_TURN_THRESHOLD * s

        if self.dragging:
            goal = self.cursor
        else:
            # 不拖就停在原地：目标点设成自己，只剩摩擦把惯性吃掉
            goal = self.pos

        dx = goal.x - self.pos.x
        dy = goal.y - self.pos.y
        dead = 3.0 * s

        if abs(dx) > dead:
            if self.vel.x > -turn:
                self.vel.x += accel if dx > 0 else -accel
            else:
                self.vel.x += (accel * 0.25) if dx > 0 else -(accel * 0.25)
        else:
            self.vel.x *= C_PET_FRICTION
            if abs(self.vel.x) <= accel:
                self.vel.x = 0.0

        if abs(dy) > dead:
            if self.vel.y > -turn:
                self.vel.y += accel if dy > 0 else -accel
            else:
                self.vel.y += (accel * 0.25) if dy > 0 else -(accel * 0.25)
        else:
            self.vel.y *= C_PET_FRICTION
            if abs(self.vel.y) <= accel:
                self.vel.y = 0.0

        self.vel.x = max(-max_speed, min(max_speed, self.vel.x))
        self.vel.y = max(-max_speed, min(max_speed, self.vel.y))

        self.pos = self.pos + self.vel * ticks
        self._confine()

        self.trail.insert(0, self.pos.copy())
        if len(self.trail) > self.TRAIL_LEN:
            self.trail.pop()

    def _wander(self, ticks):
        """不拖的时候自己慢慢晃。"""
        w = self.world
        self.retarget -= ticks
        if self.retarget <= 0:
            self.retarget = random.uniform(70.0, 220.0)
            self._goal = V(random.uniform(w.origin_x + 80, w.origin_x + w.W - 80),
                           random.uniform(w.origin_y + 80, w.ground_y - 80))
        if not hasattr(self, "_goal"):
            self._goal = V(w.origin_x + w.W * 0.5, w.origin_y + w.H * 0.42)
        return self._goal

    def _confine(self):
        w = self.world
        pad = self.SIZE * 0.8
        if self.pos.x < w.origin_x + pad:
            self.pos.x = w.origin_x + pad
            self.vel.x = abs(self.vel.x) * 0.4
        elif self.pos.x > w.origin_x + w.W - pad:
            self.pos.x = w.origin_x + w.W - pad
            self.vel.x = -abs(self.vel.x) * 0.4
        if self.pos.y < w.origin_y + pad:
            self.pos.y = w.origin_y + pad
            self.vel.y = abs(self.vel.y) * 0.4
        elif self.pos.y > w.ground_y - pad:
            self.pos.y = w.ground_y - pad
            self.vel.y = -abs(self.vel.y) * 0.4

    def speed(self):
        return self.vel.length()

    def hit(self, x, y, pad=None):
        r = pad if pad is not None else self.SIZE
        return abs(x - self.pos.x) <= r and abs(y - self.pos.y) <= r

    def bounds(self):
        r = self.SIZE * 2 + 90
        return QRect(int(self.pos.x - r), int(self.pos.y - r), r * 2, r * 2)

    def _blit_heart(self, painter, cx, cy, scale, opacity=1.0, dmg=False):
        """优先用 UT 原版素材；缺素材才退回内置像素字形。"""
        if self.pix is not None:
            pm = self.pix_dmg if (dmg and self.pix_dmg is not None) else self.pix
            w = pm.width() * scale
            h = pm.height() * scale
            if opacity < 1.0:
                painter.setOpacity(opacity)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            painter.drawPixmap(QRectF(cx - w / 2.0, cy - h / 2.0, w, h), pm,
                               QRectF(0, 0, pm.width(), pm.height()))
            if opacity < 1.0:
                painter.setOpacity(1.0)
            return
        n = len(HEART_PIX)
        unit = scale * (self.SIZE / n)
        ox = cx - len(HEART_PIX[0]) * unit / 2.0
        oy = cy - n * unit / 2.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 0, 0, int(245 * opacity)))
        for row, line in enumerate(HEART_PIX):
            for c, ch in enumerate(line):
                if ch == "1":
                    painter.fillRect(QRectF(ox + c * unit, oy + row * unit,
                                            unit + 0.6, unit + 0.6),
                                     QColor(255, 0, 0, int(245 * opacity)))

    def unit(self):
        """整数倍放大，保住 UT 素材的像素感。"""
        return max(1, int(round(self.SIZE / max(self.pix_size, 1))))

    def draw(self, painter):
        u = self.unit()
        spd = self.speed()
        # 拖动/高速时留下渐隐拖尾
        if spd > 1.0:
            n = len(self.trail)
            for i in range(n - 1, 0, -1):
                p = self.trail[i]
                a = (1.0 - i / n) * min(0.72, spd / 12.0)
                if a <= 0.04:
                    continue
                self._blit_heart(painter, p.x, p.y, u, a)
        self._blit_heart(painter, self.pos.x, self.pos.y, u, 1.0,
                         dmg=self.speed() > 9.0)


class Dust:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size",
                 "color", "gravity", "fade")

    def __init__(self, x, y, vx, vy, life, size, color, gravity):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = float(life)
        self.max_life = float(life)
        self.size = size
        self.color = color
        self.gravity = gravity
        self.fade = 1.0


class Particles:
    def __init__(self, limit=900):
        self.items = []
        self.limit = limit

    def clear(self):
        self.items.clear()

    def spawn(self, x, y, count, speed=1.0, spread=1.0, size=2.4, life=38,
              palette=DUST_SWITCH, gravity=0.0, angle=None, jitter=1.0):
        for _ in range(count):
            if len(self.items) >= self.limit:
                return
            a = random.uniform(0, math.tau) if angle is None else angle + random.uniform(-spread, spread)
            sp = random.uniform(0.35, 1.0) * speed
            vx = math.cos(a) * sp
            vy = math.sin(a) * sp
            col = random.choice(palette)
            s = size * random.uniform(0.6, 1.3)
            self.items.append(Dust(
                x + random.uniform(-jitter, jitter),
                y + random.uniform(-jitter, jitter),
                vx, vy,
                life * random.uniform(0.7, 1.2), s, col, gravity))

    def burst_switch(self, x, y, count=77):
        """ChibiiDoggo.cs：切换陆地/飞行时 77 颗 noGravity 尘，速度 ×1.5。"""
        for _ in range(count):
            if len(self.items) >= self.limit:
                break
            a = random.uniform(0, math.tau)
            sp = random.uniform(0.8, 3.0) * 1.5
            col = random.choice(DUST_SWITCH)
            r = random.randint(0, 2)
            scale = 1.0
            spd = sp
            if r == 0:
                spd *= 1.5
                scale = 0.7
            elif r == 1:
                spd *= 1.2
                scale = 0.9
            self.items.append(Dust(x, y, math.cos(a) * spd, math.sin(a) * spd,
                                   34 * random.uniform(0.8, 1.3),
                                   2.5 * scale, col, 0.0))

    def trail_dust(self, x, y, vx, vy, count=2):
        for _ in range(count):
            if len(self.items) >= self.limit:
                return
            self.items.append(Dust(
                x + random.uniform(-4, 4), y + random.uniform(-4, 4),
                vx * 0.5 + random.uniform(-0.4, 0.4),
                vy * 0.5 + random.uniform(-0.4, 0.4),
                20 * random.uniform(0.7, 1.2), 2.0 * random.uniform(0.7, 1.2),
                random.choice(DUST_GLOW), 0.0))

    def update(self, ticks=1.0):
        alive = []
        for d in self.items:
            d.x += d.vx * ticks
            d.y += d.vy * ticks
            d.vy += d.gravity * ticks
            d.vx *= 0.985
            d.vy *= 0.985
            d.life -= ticks
            if d.life > 0:
                alive.append(d)
        self.items = alive

    def draw(self, painter):
        painter.setPen(Qt.NoPen)
        for d in self.items:
            t = max(0.0, min(1.0, d.life / d.max_life))
            a = int(235 * t)
            if a <= 3:
                continue
            r, g, b = d.color
            painter.setBrush(QColor(r, g, b, a))
            s = d.size * (0.5 + t * 0.7)
            painter.drawEllipse(QPointF(d.x, d.y), s, s)


class Portal:
    """传送门：裂开 → 保持 → 收拢，神吞从里面钻出来。"""

    OPEN = 26.0
    HOLD = 95.0
    CLOSE = 28.0

    __slots__ = ("x", "y", "angle", "scale", "t", "spin", "done", "spawned")

    def __init__(self, x, y, angle=0.0, scale=1.0):
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)
        self.scale = float(scale)
        self.t = 0.0
        self.spin = 0.0
        self.done = False
        self.spawned = False

    def update(self, ticks):
        self.t += ticks
        self.spin += 0.055 * ticks
        if not self.spawned and self.t >= self.OPEN * 0.55:
            self.spawned = True
        if self.t >= self.OPEN + self.HOLD + self.CLOSE:
            self.done = True

    def phase(self):
        """返回 (不透明度, 张开度)。"""
        if self.t < self.OPEN:
            k = self.t / self.OPEN
            return k, k
        if self.t < self.OPEN + self.HOLD:
            return 1.0, 1.0
        k = (self.t - self.OPEN - self.HOLD) / self.CLOSE
        return max(0.0, 1.0 - k), 1.0


class GlowLayer:
    """叠加发光：Additive 混合绘制 Glow 遮罩层。"""

    @staticmethod
    def draw(painter, pixmap, x, y, opacity=1.0, scale=1.0, rot=0.0, flip=False):
        if pixmap is None or pixmap.isNull():
            return
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.setOpacity(opacity)
        painter.translate(x, y)
        if rot:
            painter.rotate(math.degrees(rot))
        if flip:
            painter.scale(-1.0, 1.0)
        w = pixmap.width() * scale
        h = pixmap.height() * scale
        painter.drawPixmap(QRectF(-w / 2, -h / 2, w, h), pixmap,
                           QRectF(0, 0, pixmap.width(), pixmap.height()))
        painter.restore()


def radial_glow(painter, x, y, radius, color, alpha=120):
    g = QRadialGradient(QPointF(x, y), radius)
    c = QColor(*color)
    g.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
    g.setColorAt(0.55, QColor(c.red(), c.green(), c.blue(), int(alpha * 0.35)))
    g.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(g))
    painter.drawEllipse(QPointF(x, y), radius, radius)


def remap(v, a, b, c, d):
    """Utils.Remap：把 [a,b] 区间映射到 [c,d] 并夹紧。"""
    if b == a:
        return c
    t = (v - a) / (b - a)
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return c + (d - c) * t


class LaserWall:
    """神明吞噬者的激光网（弹幕网）。

    逐行对应 CalamityMod/Projectiles/Boss/DoGLaserWalls.cs：
      laserCount  = (int)(6000 / max(laserDist, 1))
      laserLength = laserDist * laserCount / 2
      attackTime  = 30，time += attackSpeed
      开火瞬间 laserFX = 3，之后 storedTime + 10 帧内消失
      drawColor   = Lerp(Cyan, Magenta, LerpValue(endTime, storedTime, time)^2)
    """

    ATTACK_TIME = 30.0
    CYAN = (0, 255, 255)
    MAGENTA = (255, 0, 255)

    def __init__(self, x, y, attack_speed=0.5, laser_dist=250.0, laser_type=0,
                 target=None):
        self.cx = float(x)
        self.cy = float(y)
        self.attack_speed = attack_speed
        self.laser_dist = max(laser_dist, 1.0)
        self.laser_type = int(laser_type) % 6
        self.time = 0.0
        self.laser_fx = 1.0
        self.done = False
        self.stored_time = 0.0
        self.dead = False
        self.fired = False
        self.sine = 0.0
        self.draw_color = self.CYAN
        self.count = int(6000 / self.laser_dist)
        self.length = self.laser_dist * self.count / 2.0
        self.tx = target.x if target else x
        self.ty = target.y if target else y

    def update(self, ticks, target=None):
        if self.laser_fx > 0.0:
            k = 0.12 if self.time > 15.0 else 0.01
            self.laser_fx += (0.0 - self.laser_fx) * k * ticks
        self.sine = math.sin(self.time * 4.0 / math.pi)
        if target is not None:
            self.tx, self.ty = target.x, target.y

        if self.time >= self.ATTACK_TIME and not self.done:
            self.laser_fx = 3.0
            self.done = True
            self.fired = True
            self.stored_time = self.time

        end_time = self.stored_time + 10.0
        if self.time >= end_time and self.done:
            self.dead = True
            return
        if self.done:
            t = (end_time - self.time) / max(end_time - self.stored_time, 1e-6)
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            t = 1.0 - t
            t = t * t
            self.draw_color = tuple(
                int(self.CYAN[i] + (self.MAGENTA[i] - self.CYAN[i]) * t) for i in range(3))
        self.time += self.attack_speed * ticks

    def _axes(self):
        rot = math.pi / 4.0 if self.laser_type in (1, 3, 5) else 0.0
        x = (math.cos(rot), math.sin(rot))
        y = (-math.sin(rot), math.cos(rot))
        return x, y

    def beams(self):
        """生成所有激光线段：(x0,y0,x1,y1, cross)"""
        x, y = self._axes()
        out = []
        for l in range(2):
            horizontal = (l != 0)
            cross = ((self.laser_type == 2 and not horizontal) or
                     (self.laser_type == 3 and not horizontal) or
                     (self.laser_type == 4 and horizontal) or
                     (self.laser_type == 5 and horizontal))
            step = 2 if cross else 1
            for i in range(0, self.count, step):
                if horizontal:
                    sx = self.cx - y[0] * self.length
                    sy = self.cy - y[1] * self.length
                    px = sx + x[0] * (self.laser_dist * i) - x[0] * (self.laser_dist * self.count / 2.0)
                    py = sy + x[1] * (self.laser_dist * i) - x[1] * (self.laser_dist * self.count / 2.0)
                    rot = math.pi + (math.pi / 4.0 if self.laser_type in (1, 3, 5) else 0.0)
                else:
                    sx = self.cx - x[0] * self.length
                    sy = self.cy - x[1] * self.length
                    px = sx + y[0] * (self.laser_dist * i) - y[0] * (self.laser_dist * self.count / 2.0)
                    py = sy + y[1] * (self.laser_dist * i) - y[1] * (self.laser_dist * self.count / 2.0)
                    rot = math.pi / 2.0 + (math.pi / 4.0 if self.laser_type in (1, 3, 5) else 0.0)
                if cross:
                    dx, dy = self.tx - px, self.ty - py
                    ln = math.hypot(dx, dy)
                    rot = (math.atan2(dy, dx) if ln > 1e-6 else 0.0) + math.pi / 2.0
                # 贴图原点在底边中点且默认朝上，所以 rot 对应的延伸方向是 (sin, -cos)
                ex = px + math.sin(rot) * self.length
                ey = py - math.cos(rot) * self.length
                out.append((px, py, ex, ey, cross))
        return out

    def bounds(self):
        x, y = self._axes()
        r = self.length * 2.2
        return (self.cx - r, self.cy - r, r * 2.0, r * 2.0)


def laser(painter, x0, y0, x1, y1, width, core=(255, 255, 255), edge=(168, 120, 255)):
    pen = QPen(QColor(edge[0], edge[1], edge[2], 130), width * 2.4)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    pen = QPen(QColor(core[0], core[1], core[2], 235), width)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
