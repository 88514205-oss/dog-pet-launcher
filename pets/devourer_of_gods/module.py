"""神明吞噬者 · 桌宠模块实现。

本模块只依赖 host 提供的通用能力：
    host.world        屏幕几何 / 鼠标
    host.particles    粒子池
    host.portals      传送门特效列表
    host.lib          官方素材库
    host.engine       模式引擎（target / mode / consume）
    host.mode         当前模式字符串
    host.settings     持久化设置
    host.play(key)    播音效
    host.spawn_portal(x, y, angle)
    host.force_repaint()
"""

import math
import os
import random

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap, QRegion

from dogpet import assets, config as C, fx
from dogpet.ai_pet import ChibiiPet
from dogpet.ai_worm import DoGWorm
from dogpet.vec import V


def create(host):
    return DevourerPet(host)


class DevourerPet:
    """同一个桌宠的三种形象：本体长虫 / Q版 / 神吞娘。"""

    FORMS = (("dog", "神明吞噬者 · 本体"),
             ("chibii", "Q版神吞 · Chibii"),
             ("chan", "神吞娘"))

    def __init__(self, host):
        self.host = host
        self.form = host.settings.get("dogform", "dog")
        self.chibii = None
        self.worm = None
        self.chan = None
        self._laser_spawned = False
        self._laser_phase = 0.0
        self._bite_cd = 0.0
        self._charging = False
        self._off_timer = 0.0
        self._talk_timer = random.uniform(700, 1900)
        self._ensure()

    # ---- 形态 -----------------------------------------------------------
    def _ensure(self):
        host = self.host
        ps = host.world.pixel_scale
        if self.form == "dog":
            if self.worm is None:
                self.worm = DoGWorm(host.world, ps(host.scale_dog))
        elif self.form == "chibii":
            if self.chibii is None:
                self.chibii = ChibiiPet(host.world, ps(host.scale_chibii))
        elif self.chan is None:
            self.chan = Dogchan(host)

    def set_form(self, form):
        if form == self.form:
            return
        self.form = form
        self.host.settings["dogform"] = form
        self._ensure()
        self.recenter()

    def scale_for(self, form):
        return self.host.scale_chibii if form == "chibii" else self.host.scale_dog

    def set_scale(self, form, value):
        ps = self.host.world.pixel_scale
        if form == "chibii" and self.chibii is not None:
            self.chibii.scale = ps(value)
        elif form == "dog" and self.worm is not None:
            self.worm.scale = ps(value)
            self.worm._sync_segments_line()

    # ---- 生命周期 -------------------------------------------------------
    def recenter(self):
        host = self.host
        if self.form == "chan":
            self.chan.recenter()
            host.play("spawn")
            host.play("teleport")
            host.force_repaint()
            return
        if self.form == "dog":
            self.worm.c = V(host.world.origin_x + host.world.W * 0.5,
                            host.world.origin_y + host.world.H * 0.5)
            self.worm.vel = V()
            self.worm._collapse()
            self._enter_burst = 85.0
            self.worm.portal_burst = 85.0
        else:
            p = self.chibii
            p.pos = V(host.world.origin_x + host.world.W * 0.5,
                      host.world.ground_y - 260)
            p.vel = V(4.0 * p.scale, 0.0)
            p.on_ground = False
            p.fly_mode = True
        host.spawn_portal(self._entry_point().x, self._entry_point().y, 0.0)
        host.play("spawn")
        host.play("teleport")
        host.force_repaint()

    def _entry_point(self):
        host = self.host
        if self.form == "dog" and self.worm is not None:
            return self.worm.c
        if self.form == "chan":
            return self.chan.center()
        return V(host.world.origin_x + host.world.W * 0.5,
                 host.world.origin_y + host.world.H * 0.5)

    def detach(self):
        pass

    # ---- 每 tick ---------------------------------------------------------
    def update(self, ticks):
        if self.form == "chibii":
            self._step_chibii(ticks)
        elif self.form == "chan":
            self.chan.update(ticks)
        else:
            self._step_worm(ticks)
        self._check_mouse_bite(ticks)

    def _step_chibii(self, ticks):
        host = self.host
        pet = self.chibii
        engine = host.engine
        was_fly = pet.fly_mode
        pet.update(engine.target, ticks)
        if was_fly != pet.fly_mode:
            host.particles.burst_switch(pet.center.x, pet.center.y,
                                        C.STATE_SWITCH_DUST)
        if pet.fly_mode:
            host.particles.trail_dust(pet.center.x, pet.center.y,
                                      -pet.vel.x * 0.5, -pet.vel.y * 0.5, 1)
        elif pet.on_ground and abs(pet.vel.x) > 1.0:
            host.particles.trail_dust(pet.center.x,
                                      pet.center.y + pet.h * pet.scale * 0.4, 0, 0, 1)
        self._talk_timer -= ticks
        if self._talk_timer <= 0:
            self._talk_timer = random.uniform(700, 1900)
            host.play(random.choice(("laugh", "hurt", "jump", "seg1")))
        if engine.mode == C.MODE_DEVOUR:
            got = engine.consume(pet.center, 26.0 * pet.scale)
            if got:
                host.particles.spawn(pet.center.x, pet.center.y, 22, speed=4.5,
                                     size=3.0, life=40, palette=fx.DUST_DEVOUR)
                pet.scale = min(pet.scale * random.uniform(1.02, 1.06),
                                host.world.pixel_scale(host.scale_chibii) * 1.7)

    def _step_worm(self, ticks):
        host = self.host
        wm = self.worm
        engine = host.engine
        if engine.mode == C.MODE_DEVOUR:
            got = engine.consume(wm.c, 34.0 * wm.scale)
            if got:
                host.particles.spawn(wm.c.x, wm.c.y, 30, speed=6.0, size=3.4,
                                     life=46, palette=fx.DUST_DEVOUR)
                host.play("death")
                wm.count = min(wm.count + got, 64)
                while len(wm.segments) < wm.count:
                    wm.segments.append(type(wm.segments[0])(wm.c.x, wm.c.y))
                    wm.count = len(wm.segments)
        wm.update(engine.target, ticks,
                  wander=(engine.mode in (C.MODE_FOLLOW, C.MODE_SKY)))
        self._laser_phase += ticks

        if wm.charge_timer > 0 and not self._charging:
            self._charging = True
            host.play("jump")
            host.particles.spawn(wm.c.x, wm.c.y, 24, speed=7.0, size=3.6,
                                 life=40, palette=fx.DUST_GLOW)
        elif wm.charge_timer <= 0:
            self._charging = False

        if wm.state == 2:
            if not self._laser_spawned:
                self._laser_spawned = True
                self._spawn_laser_wall(wm)
        else:
            self._laser_spawned = False

        n = len(wm.segments)
        if n:
            for _ in range(2):
                seg = wm.segments[random.randint(0, min(6, n - 1))]
                host.particles.trail_dust(seg.c.x, seg.c.y, 0, 0, 1)
        if wm.state == 2 and random.random() < 0.02:
            host.play("beam")
        if wm.charge_timer > 0 and random.random() < 0.35:
            host.particles.spawn(wm.c.x, wm.c.y, 3, speed=2.4, size=3.2, life=26,
                                 palette=fx.DUST_GLOW)

    # ---- 鼠标受击 --------------------------------------------------------
    def _check_mouse_bite(self, ticks):
        self._bite_cd -= ticks
        if self._bite_cd > 0:
            return
        host = self.host
        tp = host.engine.target.pos
        if self.form == "dog" and self.worm is not None:
            head = self.worm.c
            reach = 56.0 * self.worm.scale
        elif self.form == "chan":
            head = self.chan.center()
            reach = 52.0
        else:
            head = self.chibii.center
            reach = 38.0 * self.chibii.scale
        if head.distance(tp) > reach:
            return
        self._bite_cd = 58.0
        host.play("hurt")
        host.play(random.choice(("seg1", "seg2", "seg3", "seg4")))
        host.particles.spawn(tp.x, tp.y, 20, speed=4.8, size=3.2, life=34,
                             palette=fx.DUST_DEVOUR)

    # ---- 出屏召回 --------------------------------------------------------
    def tick_world(self, ticks):
        """需要窗口/世界级判断的部分（出屏太久就召回）。"""
        if self.form != "dog" or self.worm is None:
            return
        w = self.host.world
        hx, hy = self.worm.c.x, self.worm.c.y
        margin = 430.0
        if (w.origin_x - margin < hx < w.origin_x + w.W + margin and
                w.origin_y - margin < hy < w.ground_y + margin):
            self._off_timer = 0.0
            return
        self._off_timer += ticks
        if self._off_timer > 700.0:
            self._off_timer = 0.0
            self.recenter()

    # ---- 激光网 ----------------------------------------------------------
    def _spawn_laser_wall(self, wm):
        host = self.host
        lw = fx.LaserWall(wm.c.x, wm.c.y, attack_speed=0.5,
                          laser_dist=250.0 * wm.scale,
                          laser_type=random.randint(0, 5),
                          target=V(wm.c.x, wm.c.y))
        host.laser_walls.append(lw)
        if len(host.laser_walls) > 4:
            host.laser_walls.pop(0)
        host.play("wall_spawn")

    # ---- 脏区 ------------------------------------------------------------
    def bounds(self):
        """返回内容的全局脏区 region（host 据此决定重绘范围）。"""
        if self.form == "chibii":
            return QRegion(self._chibii_aabb().toAlignedRect())
        if self.form == "chan":
            return self.chan.bounds()
        wm = self.worm
        if wm is None:
            return QRegion(self.host.world.work)
        s = wm.scale
        w = self.host.world
        rects = []
        sizes = {}
        view = QRectF(w.origin_x - 400, w.origin_y - 400, w.W + 800, w.H + 800)
        for c, rot, kind in wm.segments_with_head():
            if kind not in sizes:
                pm = self._dog_pixmap(kind)
                sizes[kind] = (pm.width() if pm else 0, pm.height() if pm else 0)
            pw, ph = sizes[kind]
            if pw == 0 or not view.contains(QPointF(c.x, c.y)):
                continue
            pad = 130 if kind == -1 else 40
            hw = pw * s * 0.5 + pad
            hh = ph * s * 0.5 + pad
            rects.append(QRect(int(c.x - hw), int(c.y - hh), int(hw * 2), int(hh * 2)))
        reg = QRegion()
        if rects:
            cur = rects[0]
            for r in rects[1:]:
                u = cur.united(r)
                if (u.width() * u.height() <=
                        (cur.width() * cur.height() + r.width() * r.height())
                        * C.REGION_MERGE_FACTOR):
                    cur = u
                else:
                    reg = reg.united(QRegion(cur))
                    cur = r
            reg = reg.united(QRegion(cur))
        if self.host.engine.mode == C.MODE_DEVOUR:
            for st in self.host.engine.stars:
                reg = reg.united(QRegion(QRect(int(st.pos.x - 46), int(st.pos.y - 46),
                                               92, 92)))
        if reg.isEmpty():
            pm = self._dog_pixmap(-1)
            hw = (pm.width() * s * 0.5 + 120) if pm is not None else 150
            reg = QRegion(QRect(int(wm.c.x - hw), int(wm.c.y - hw),
                                int(hw * 2), int(hw * 2)))
        return reg

    def _chibii_aabb(self):
        p = self.chibii
        s = p.scale
        cx = p.pos.x + p.w * s * 0.5
        cy = p.pos.y + p.h * s * 0.5
        xs = [cx]
        ys = [cy]
        for op in p.old_pos:
            xs.append(op.x + p.w * s * 0.5)
            ys.append(op.y + p.h * s * 0.5)
        rad = max(C.CHIBII_FRAME_SIZE[0], C.CHIBII_HITBOX[0],
                  C.CHIBII_FLY_FRAME_SIZE[0]) * s * 0.7
        pad = 170.0
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return QRectF(x0 - rad - pad, y0 - rad - pad,
                      (x1 - x0) + (rad + pad) * 2.0,
                      (y1 - y0) + (rad + pad) * 2.0)

    def render_box(self):
        """用于鼠标命中的包围盒（全局坐标 x, y, w, h）。"""
        if self.form == "chibii":
            x, y, bw, bh = self.chibii.hitbox()
            return (x - 14, y - 14, bw + 28, bh + 28)
        if self.form == "chan":
            return self.chan.render_box()
        wm = self.worm
        if wm is None:
            return (0.0, 0.0, 10.0, 10.0)
        s = wm.scale
        sizes = []
        for c, rot, kind in wm.segments_with_head():
            pm = self._dog_pixmap(kind)
            if pm is None:
                continue
            sizes.append((c.x, c.y, pm.width() * s, pm.height() * s))
        if not sizes:
            return (0.0, 0.0, 10.0, 10.0)
        x0 = min(v[0] - v[2] / 2 for v in sizes)
        y0 = min(v[1] - v[3] / 2 for v in sizes)
        x1 = max(v[0] + v[2] / 2 for v in sizes)
        y1 = max(v[1] + v[3] / 2 for v in sizes)
        return (x0 - 10, y0 - 10, (x1 - x0) + 20, (y1 - y0) + 20)

    def pet_position(self):
        if self.form == "chibii":
            return V(self.chibii.pos.x, self.chibii.pos.y)
        if self.form == "chan":
            return self.chan.pet_position()
        return V(self.worm.c.x, self.worm.c.y)

    def place(self, gx, gy):
        if self.form == "chibii":
            self.chibii.pos = V(gx, gy)
            self.chibii.vel = V()
            self.chibii.on_ground = False
        elif self.form == "chan":
            self.chan.place(gx, gy)
        else:
            wm = self.worm
            dx = gx - wm.c.x
            dy = gy - wm.c.y
            wm.c = V(gx, gy)
            for s in wm.segments:
                s.c = V(s.c.x + dx, s.c.y + dy)
            wm.vel = V()

    # ---- 绘制 ------------------------------------------------------------
    def draw(self, p, host):
        if self.form == "chibii":
            self._draw_chibii(p, host)
        elif self.form == "chan":
            self.chan.draw(p, host)
        else:
            self._draw_worm(p, host)

    @staticmethod
    def _blit(p, pm, cx, cy, dw, dh, rot, sprite_dir):
        p.save()
        p.translate(cx, cy)
        if rot:
            p.rotate(math.degrees(rot))
        if sprite_dir < 0:
            p.scale(-1.0, 1.0)
        p.drawPixmap(QRectF(-dw / 2, -dh / 2, dw, dh), pm,
                     QRectF(0, 0, pm.width(), pm.height()))
        p.restore()

    def _dog_pixmap(self, kind):
        lib = self.host.lib
        parts = lib.dog_p2 if (self.worm and self.worm.phase2) else lib.dog_p1
        if kind == -1:
            return parts.get("head")
        if kind == 1:
            return parts.get("tail")
        return parts.get("body")

    def _draw_chibii(self, p, host):
        pet = self.chibii
        lib = host.lib
        s = pet.scale
        frames = lib.fly if pet.fly_mode else lib.chibii
        idx = min(max(pet.frame, 0), len(frames) - 1)
        pm = frames[idx]
        mono_frames = lib.fly_mono if pet.fly_mode else lib.chibii_mono
        mono = mono_frames[min(idx, len(mono_frames) - 1)]

        dw = pm.width() * C.CHIBII_SCALE * s
        dh = pm.height() * C.CHIBII_SCALE * s
        cx = pet.pos.x + pet.w * s * 0.5
        cy = pet.pos.y + pet.h * s * 0.5

        trail_len = C.TRAIL_FLY_LEN if pet.fly_mode else C.TRAIL_LAND_LEN
        start = C.TRAIL_FLY_START if pet.fly_mode else C.TRAIL_LAND_START
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        for i in range(1, start, C.TRAIL_STEP):
            if i >= len(pet.old_pos):
                break
            a = (start - i) / (trail_len * C.TRAIL_ALPHA_DIV)
            if a <= 0.02:
                continue
            op = pet.old_pos[i]
            p.save()
            p.setOpacity(min(0.85, a * 3.4))
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            self._blit(p, mono, op.x + pet.w * s * 0.5, op.y + pet.h * s * 0.5,
                       dw, dh, pet.old_rot[i], pet.sprite_direction)
            p.restore()

        if pet.fly_mode:
            fx.radial_glow(p, cx, cy, dw * 0.85, (150, 108, 255), 70)
        self._blit(p, pm, cx, cy, dw, dh, pet.rotation, pet.sprite_direction)

    def _draw_worm(self, p, host):
        wm = self.worm
        if wm is None:
            return
        s = wm.scale
        parts = host.lib.dog_p2 if wm.phase2 else host.lib.dog_p1
        head = parts.get("head")
        body = parts.get("body")
        tail = parts.get("tail")

        segs = list(wm.segments_with_head())
        for k in range(len(segs) - 1, -1, -1):
            c, rot, kind = segs[k]
            pm = head if kind == -1 else (tail if kind == 1 else body)
            if pm is None:
                continue
            dw = pm.width() * s
            dh = pm.height() * s
            if kind == -1:
                fx.radial_glow(p, c.x, c.y, dw * 0.85, (150, 90, 255), 60)
            self._blit(p, pm, c.x, c.y, dw, dh, rot, 1)

        glow_head = parts.get("head_glow")
        glow_body = parts.get("body_glow")
        if glow_head is not None or glow_body is not None:
            op = 0.30 + 0.35 * wm.glow
            if op > 0.02:
                n = len(segs)
                k = min(C.GLOW_SEGMENTS, n)
                glow_list = segs[:k] + (segs[-3:] if n > k + 3 else [])
                p.save()
                p.setCompositionMode(QPainter.CompositionMode_Plus)
                p.setOpacity(op)
                for c, rot, kind in glow_list:
                    gm = glow_head if kind == -1 else glow_body
                    if gm is None:
                        continue
                    dw = gm.width() * s
                    dh = gm.height() * s
                    self._blit(p, gm, c.x, c.y, dw, dh, rot, 1)
                p.restore()

        if wm.state == 2:
            self._draw_laser(p, host)
        if wm.charge_timer > 0:
            fx.radial_glow(p, wm.c.x, wm.c.y, 90 * s + 30, (255, 120, 200), 90)

    def _draw_laser(self, p, host):
        target = host.engine.target.pos
        t = self._laser_phase
        n = 8
        for i in range(n):
            ang = (i / n) * math.tau + t * 0.012
            fx.laser(p, target.x + math.cos(ang) * 120.0,
                     target.y + math.sin(ang) * 120.0,
                     target.x + math.cos(ang) * 900.0,
                     target.y + math.sin(ang) * 900.0, 1.6)

    # ---- 模块选项 --------------------------------------------------------
    def options(self):
        return [
            {"type": "choice", "key": "form", "label": "形态",
             "choices": [v for _k, v in self.FORMS],
             "value": dict(self.FORMS)[self.form]},
        ]

    def set_option(self, key, value):
        if key == "form":
            for k, label in self.FORMS:
                if label == value:
                    self.set_form(k)
                    return


class Dogchan:
    """神吞娘：二创像素娘化形象，10 帧待机循环，飘在鼠标上方。"""

    FRAMES = 10
    TICK_PER_FRAME = 6.0
    HOVER = 46.0 * 2.2

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

    def _size(self):
        if not self.frames:
            return (40.0, 40.0)
        return (self.frames[0].width() * self.scale,
                self.frames[0].height() * self.scale)

    def center(self):
        w, h = self._size()
        return V(self.pos.x + w * 0.5, self.pos.y + h * 0.5)

    def update(self, ticks):
        host = self.host
        w = host.world
        self.bob += 0.045 * ticks
        want = host.engine.target.pos
        tx = want.x
        ty = want.y - self.HOVER + math.sin(self.bob) * 14.0 * self.scale
        self.vel.x += ((tx - self.pos.x) * 0.9 - self.vel.x) * 0.055 * ticks
        self.vel.y += ((ty - self.pos.y) * 0.9 - self.vel.y) * 0.055 * ticks
        self.pos.x += self.vel.x * ticks
        self.pos.y += self.vel.y * ticks
        sw, sh = self._size()
        self.pos.x = max(w.origin_x - 40, min(self.pos.x, w.origin_x + w.W - sw + 40))
        self.pos.y = max(w.origin_y - 40, min(self.pos.y, w.ground_y - sh + 40))
        self.counter += ticks
        while self.counter >= self.TICK_PER_FRAME:
            self.counter -= self.TICK_PER_FRAME
            self.frame = (self.frame + 1) % max(len(self.frames), 1)
        c = self.center()
        if abs(self.vel.x) + abs(self.vel.y) > 3.0 and random.random() < 0.35:
            host.particles.trail_dust(c.x, c.y, -self.vel.x * 0.3,
                                      -self.vel.y * 0.3, 1)

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

    def draw(self, p, host):
        if not self.frames:
            return
        pm = self.frames[min(self.frame, len(self.frames) - 1)]
        w, h = self._size()
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawPixmap(QRectF(self.pos.x, self.pos.y, w, h), pm,
                     QRectF(0, 0, pm.width(), pm.height()))
