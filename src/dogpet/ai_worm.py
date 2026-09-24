"""神明吞噬者本体 AI：头部三态行为 + 链式体节跟随。

头部移动算法逐行直译 DevourerofGodsHead.cs 的追踪段；
体节跟随逐行直译 DevourerofGodsBody.cs 第 257~267 行。
"""

import bisect
import math
import random

from . import config as C
from .vec import (V, HALF_PI, PI, wrap_angle, clamp, from_rotation)

STATE_PASSIVE = 0
STATE_AGGRESSIVE = 1
STATE_LASER = 2


class Segment:
    __slots__ = ("c", "rot", "type")

    def __init__(self, x, y, rot=0.0, kind=0):
        self.c = V(x, y)
        self.rot = rot
        self.type = kind


class DoGWorm:
    """scale 同时作用于尺寸与速度，保持游戏内相对关系不变。"""

    def __init__(self, world, scale=0.4, count=None):
        self.world = world
        self.scale = scale
        self.count = count if count else C.DOG_SEGMENT_COUNT
        x = world.origin_x + world.W * 0.5
        y = world.origin_y + world.H * 0.5
        self.c = V(x, y)
        self.vel = V()
        self.rot = HALF_PI
        self.life_ratio = 1.0
        self.phase2 = False
        self.state = STATE_PASSIVE
        self.phase_timer = 0.0
        self.laser_timer = 0.0
        self.charge_timer = 0.0
        self.charge_cooldown = 0.0
        self.post_teleport = 0.0
        self.segments = [Segment(x, y) for _ in range(self.count)]
        self.wave = 0.0
        self.orbit = 0.0
        self.wander = 0.0
        self.wander_mode = True
        self.cruise_pt = None
        self.cruise_stall = 0.0
        self.portal_burst = 0.0
        self.unfold = 1.0
        self.position_set = False
        self.jaw = 0.0
        self.glow = 0.0
        self.trail = []
        self.path_points = []
        self._sync_segments_line()

    def _lay_spiral(self):
        """按等弧长螺线铺开初始虫身，避免首帧叠成一团。"""
        spacing = self.spacing()
        a = self.rot
        segs = self.segments
        for i, s in enumerate(segs):
            r = spacing * (0.9 + i * 0.055)
            s.c = V(self.c.x + math.cos(a) * r, self.c.y + math.sin(a) * r)
            s.rot = a + HALF_PI
            a += spacing / max(r, 1e-3)

    def spacing(self):
        base = C.DOG_SEGMENT_SPACING_P2 if self.phase2 else C.DOG_SEGMENT_SPACING
        return base * self.scale * max(self.unfold, 0.04)

    def _sync_segments_line(self):
        """把虫身重置成一条轻微起伏的长蛇（不是死直线），并预填路径点。"""
        spacing = self.spacing()
        total = max(self.count * spacing, 1.0)
        h = self.rot - HALF_PI
        dx, dy = math.cos(h), math.sin(h)
        px, py = -dy, dx
        amp = min(150.0 * self.scale, total * 0.06)
        wave = 0.55 / max(self.scale, 0.1)
        self.path_points = [self.c.copy()]
        step = 6.0
        k = int(total / step) + 2
        for i in range(1, k + 1):
            d = step * i
            off = math.sin(d * 0.0022 * wave) * amp * (d / total)
            self.path_points.append(V(self.c.x - dx * d + px * off,
                                      self.c.y - dy * d + py * off))
        for i, s in enumerate(self.segments):
            d = (i + 1) * spacing
            t = d / total
            off = math.sin(d * 0.0022 * wave) * amp * t
            s.c = V(self.c.x - dx * d + px * off, self.c.y - dy * d + py * off)
            nxt = V(self.c.x - dx * (d + 12.0) + px * math.sin((d + 12.0) * 0.0022 * wave) * amp * ((d + 12.0) / total),
                    self.c.y - dy * (d + 12.0) + py * math.sin((d + 12.0) * 0.0022 * wave) * amp * ((d + 12.0) / total))
            s.rot = (nxt - s.c).to_rotation() + HALF_PI
        self.unfold = 1.0

    def _speed(self):
        base = C.DOG_SEGMENT_VELOCITY
        if self.phase2:
            base += C.DOG_SEG_VEL_SCALING * self._decay()
        return base

    def _decay(self):
        return 1.0 - (self.life_ratio * 0.75 + 0.25)

    def homing_speed(self):
        s = C.DOG_HOMING_SPEED + C.DOG_LIFE_SCALING * self._decay()
        return s * self.scale

    def turn_speed(self):
        t = C.DOG_TURN_SPEED + C.DOG_TURN_SCALING * self._decay()
        return t * self.scale

    def segment_velocity(self):
        return self._speed() * self.scale

    def charge_velocity(self):
        return C.DOG_CHARGE_VELOCITY * C.DOG_CHARGE_MULT * self.scale

    def set_state(self, state):
        if state == self.state:
            return
        self.state = state
        self.phase_timer = 0.0

    def update(self, target, ticks=1.0, wander=True):
        self.wave += 0.16 * ticks
        self.orbit += 0.062 * ticks
        if self.unfold < 1.0:
            self.unfold = min(1.0, self.unfold + 0.016 * ticks)
        self.phase_timer += ticks
        self.life_ratio = target.life_ratio if hasattr(target, "life_ratio") else self.life_ratio

        dist = self.c.distance(target.pos)
        limit = C.DOG_PHASE_PASSIVE
        if self.state == STATE_LASER:
            limit = C.DOG_PHASE_LASER           # 激光阶段 300 帧（源码 idleCounterMax）
        elif self.phase2:
            limit = max(C.DOG_PHASE_MIN, int(limit / (1 + (1 - self.life_ratio) * 5)))
        if dist > C.DOG_CATCHUP_DIST:
            self.set_state(STATE_AGGRESSIVE)
        elif self.phase_timer > limit:
            if self.state == STATE_PASSIVE:
                self.set_state(STATE_AGGRESSIVE)
            elif self.state == STATE_AGGRESSIVE:
                self.set_state(STATE_LASER)
                self.laser_timer = C.DOG_PHASE_LASER
            else:
                self.set_state(STATE_PASSIVE)

        if self.state == STATE_LASER:
            self._laser_move(target, ticks)
        elif self.state == STATE_AGGRESSIVE:
            self._aggressive_move(target, ticks)
        else:
            self._passive_move(target, ticks)

        if self.portal_burst > 0:
            # 出场演出：沿出场方向直线游出，把虫身从门里抽出来
            self.portal_burst -= ticks
            self.vel = from_rotation(self.rot - HALF_PI) * self.homing_speed() * 0.55
        if self.post_teleport > 0:
            self.post_teleport -= ticks

        # 只有真的跑丢了才瞬移回来；正常越出屏幕游动不算跑丢
        w = self.world
        far = (self.c.x < w.origin_x - 1600.0 or self.c.x > w.origin_x + w.W + 1600.0 or
               self.c.y < w.origin_y - 1300.0 or self.c.y > w.ground_y + 1300.0)
        if dist > C.DOG_CATCHUP_DIST * 2.2 or far:
            self.teleport_near(target.pos)

        if self.vel.length_sq() > 0.05:
            goal = math.atan2(self.vel.y, self.vel.x) + HALF_PI
            self.rot += wrap_angle(goal - self.rot) * 0.45
        if self.position_set:
            self.position_set = False
        else:
            self.c = self.c + self.vel * ticks
        self._confine()
        self._update_segments(ticks)
        self._update_trail()

        self.jaw = (math.sin(self.wave * 1.6) + 1.0) * 0.5
        self.glow = 0.55 + 0.45 * math.sin(self.wave * 2.3)

    # ---- 头部行为 -------------------------------------------------------
    def _orbit_params(self, target):
        """跑道轨道参数。中心允许越出屏幕，使神吞能在屏幕边缘游进游出，
        而不是被硬墙挡住——屏幕外活动正是本体该有的样子。"""
        w = self.world
        b = min(w.H * 0.34, (w.H - 100.0) * 0.5)
        a = min(w.W * 0.40, (w.W - 100.0) * 0.5)
        a = max(a, b)
        over_x = a * 0.45
        over_y = b * 0.45
        cx = clamp(target.pos.x, w.origin_x - over_x, w.origin_x + w.W + over_x)
        cy = clamp(target.pos.y, w.origin_y - over_y, w.ground_y + over_y)
        return cx, cy, a, b

    def _orbit_point_at(self, cx, cy, a, b, s):
        """跑道形轨道（两端半圆 + 两条直道），s 为弧长参数。"""
        straight = max(a - b, 0.0)
        per = 4.0 * straight + math.tau * b
        s = s % per
        L = 2.0 * straight
        if s < L:
            return V(cx - straight + s, cy + b)
        s -= L
        H = math.pi * b
        if s < H:
            ang = s / b - HALF_PI
            return V(cx + straight + b * math.cos(ang), cy + b * math.sin(ang))
        s -= H
        if s < L:
            return V(cx + straight - s, cy - b)
        s -= L
        ang = s / b + HALF_PI
        return V(cx - straight + b * math.cos(ang), cy + b * math.sin(ang))

    def _orbit_step(self, target, ticks, speed_scale=1.0):
        """头部沿跑道轨道匀速前进；冲刺后离轨时按速度平滑飞回，绝不瞬移。"""
        cx, cy, a, b = self._orbit_params(target)
        speed = self.homing_speed() * 0.55 * speed_scale
        self.orbit += speed * ticks
        nxt = self._orbit_point_at(cx, cy, a, b, self.orbit)
        delta = nxt - self.c
        d = delta.length()
        if d <= 1e-6:
            self.vel = V()
            self.c = nxt
            self.position_set = True
            return
        if d > speed * 2.0:
            self.vel = delta.normalized() * speed
            return
        self.vel = delta * (1.0 / max(ticks, 1e-6))
        self.c = nxt
        self.position_set = True

    def _pick_cruise(self, center):
        """巡航点：多数落在屏幕外的对侧，让头部横穿屏幕后从幕外折返。
        这样虫身大部分留在屏幕外，屏幕里看到的永远是一条长蛇而不是一团。"""
        w = self.world
        if random.random() < 0.15:
            ang = random.uniform(0.0, math.tau)
            r = random.uniform(0.90, 1.35) * math.hypot(w.W, w.H) * 0.45
            x = clamp(center.x + math.cos(ang) * r,
                      w.origin_x + 160.0, w.origin_x + w.W - 160.0)
            y = clamp(center.y + math.sin(ang) * r * 0.62,
                      w.origin_y + 160.0, w.ground_y - 160.0)
        else:
            side = 1 if center.x < w.origin_x + w.W * 0.5 else -1
            x = (w.origin_x + w.W + 1150.0) if side > 0 else (w.origin_x - 1150.0)
            y = clamp(center.y + random.uniform(-320.0, 320.0),
                      w.origin_y + 160.0, w.ground_y - 160.0)
        self.cruise_pt = V(x, y)

    def _cruise_point(self, center):
        if self.cruise_pt is None:
            self._pick_cruise(center)
        return self.cruise_pt

    def _cruise_step(self, target, ticks, speed_scale=0.6):
        """巡航：朝下一个点直线游动。头部横穿屏幕、在幕外折返，
        虫身被拉成一条长蛇，且大部分时间待在屏幕外。"""
        pt = self._cruise_point(target.pos)
        self.cruise_stall += ticks
        if self.c.distance(pt) < 150.0 * self.scale or self.cruise_stall > 720.0:
            self._pick_cruise(target.pos)
            self.cruise_stall = 0.0
            pt = self._cruise_point(target.pos)
        self._hunt_step(pt, ticks, speed_scale)

    def _hunt_step(self, point, ticks, speed_scale=0.5):
        """平滑追踪目标点：速度与加速度双重限幅，不会抖动也不会缩成一团。"""
        speed = self.homing_speed() * speed_scale
        delta = point - self.c
        d = delta.length()
        if d <= 1e-4:
            desired = V()
        else:
            want = speed * min(1.0, d / 150.0)
            desired = delta * (want / d)
        acc = max(self.turn_speed() * 7.0, 0.02) * ticks
        dv = desired - self.vel
        dl = dv.length()
        if dl > acc:
            dv = dv * (acc / dl)
        self.vel = self.vel + dv
        self.position_set = False

    def _collapse(self):
        """收进传送门：路径塌缩到门口，只留一小段朝后方的引线，
        体节随后被头部带出的路径一节节抽出来。"""
        h = self.rot - HALF_PI
        dx, dy = math.cos(h), math.sin(h)
        self.path_points = [self.c.copy()]
        for i in range(1, 30):
            self.path_points.append(V(self.c.x - dx * 9.0 * i,
                                      self.c.y - dy * 9.0 * i))
        self.unfold = 0.05

    def enter_from_portal(self, pos, heading=None):
        """从传送门钻出：先团在门口，再用一段强制游出把虫身拉出来。"""
        h = heading if heading is not None else 0.0
        self.rot = h + HALF_PI
        self.c = V(pos.x, pos.y)
        self.vel = from_rotation(h) * self.homing_speed() * 0.55
        self.orbit = 0.0
        self.charge_timer = 0.0
        self.charge_cooldown = 150.0
        self.post_teleport = 40.0
        self.portal_burst = 85.0
        self.cruise_pt = None
        self.cruise_stall = 0.0
        self._collapse()

    def _passive_move(self, target, ticks):
        """被动阶段：逐行直译 Head.cs 的追踪转向（homingSpeed / turnSpeed 原值）。"""
        self.charge_cooldown = max(0.0, self.charge_cooldown - ticks)
        self._steer(target.pos, self.homing_speed(), self.turn_speed(), ticks)

    def _laser_move(self, target, ticks):
        self.laser_timer -= ticks
        self._steer(target.pos, self.homing_speed() * 1.05, self.turn_speed() * 1.15, ticks)

    def _aggressive_move(self, target, ticks):
        """激进阶段：追踪提速 + 周期性冲刺（chargeVelocity 原值）。"""
        self.charge_cooldown = max(0.0, self.charge_cooldown - ticks)
        if self.charge_timer > 0:
            self.charge_timer -= ticks
            return
        if self.charge_cooldown <= 0 and self.c.distance(target.pos) < 620.0 * self.scale:
            self._begin_charge(target.pos)
            return
        self._steer(target.pos, self.homing_speed() * 1.35, self.turn_speed() * 1.5, ticks)

    def _begin_charge(self, tp):
        d = tp - self.c
        if d.length() < 1e-3:
            return
        self.vel = d.normalized() * self.charge_velocity()
        self.charge_timer = C.DOG_CHARGE_DIST * self.scale / max(self.charge_velocity(), 1e-3)
        self.charge_cooldown = 260.0
        self.post_teleport = self.charge_timer

    def _hover_offset(self, target):
        cx, cy, a, b = self._orbit_params(target)
        return self._orbit_point_at(cx, cy, a, b, self.orbit)

    def teleport_near(self, p):
        ang = random.uniform(0, math.tau)
        r = 340.0 * self.scale
        self.c = self.world.clamp_to_work(
            V(p.x + math.cos(ang) * r, p.y + math.sin(ang) * r * 0.6))
        self.vel = V()
        self._sync_segments_line()
        self.post_teleport = 30.0

    # ---- 逐行直译 Head.cs 1674~1752 的转向算法 ---------------------------
    def _steer(self, destination, speed, turn, ticks=1.0):
        v = self.vel
        tx = destination.x - self.c.x
        ty = destination.y - self.c.y
        dist = math.hypot(tx, ty)
        if dist < 34.0:
            self.vel = self.vel * 0.86          # 贴到目标点后平滑停住，原地不抖
            if self.vel.length_sq() < 0.04:
                self.vel = V()
            return
        if dist < 1e-4:
            return
        k = speed / dist
        k *= min(1.0, dist / 240.0)          # 贴近目标点时收敛速度，避免过冲来回抖
        tx *= k
        ty *= k
        a_tx, a_ty = abs(tx), abs(ty)
        # 源码为 turnSpeedCopy *= Distance / 1000；桌宠保留下限避免贴脸时停住发抖
        turn *= clamp(dist / 1000.0, 0.28, 1.0)
        turn *= ticks
        if turn <= 0.0:
            return

        def sign(x):
            return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)

        same_dir = ((v.x > 0 and tx > 0) or (v.x < 0 and tx < 0) or
                    (v.y > 0 and ty > 0) or (v.y < 0 and ty < 0))
        if same_dir:
            if v.x < tx:
                v.x += turn
            elif v.x > tx:
                v.x -= turn
            if v.y < ty:
                v.y += turn
            elif v.y > ty:
                v.y -= turn
            if a_ty < speed * 0.2 and ((v.x > 0 and tx < 0) or (v.x < 0 and tx > 0)):
                v.y += turn * 2.0 * sign(v.y)
            if a_tx < speed * 0.2 and ((v.y > 0 and ty < 0) or (v.y < 0 and ty > 0)):
                v.x += turn * 2.0 * sign(v.x)
        if not same_dir:
            if a_tx > a_ty:
                if v.x < tx:
                    v.x += turn * 1.1
                elif v.x > tx:
                    v.x -= turn * 1.1
                if (abs(v.x) + abs(v.y)) < speed * 0.5:
                    v.y += turn * sign(v.y)
            else:
                if v.y < ty:
                    v.y += turn * 1.1
                elif v.y > ty:
                    v.y -= turn * 1.1
                if (abs(v.x) + abs(v.y)) < speed * 0.5:
                    v.x += turn * sign(v.x)

    def _confine(self):
        """软边界：允许虫身有相当一部分在屏幕外游动，跑太远才平滑拉回，绝不反弹。"""
        w = self.world
        pad = 1250.0 * self.scale
        lo_x = w.origin_x - pad
        hi_x = w.origin_x + w.W + pad
        lo_y = w.origin_y - pad
        hi_y = w.ground_y + pad
        if self.c.x < lo_x:
            self.c.x = lo_x
            if self.vel.x < 0.0:
                self.vel.x *= 0.3
        elif self.c.x > hi_x:
            self.c.x = hi_x
            if self.vel.x > 0.0:
                self.vel.x *= 0.3
        if self.c.y < lo_y:
            self.c.y = lo_y
            if self.vel.y < 0.0:
                self.vel.y *= 0.3
        elif self.c.y > hi_y:
            self.c.y = hi_y
            if self.vel.y > 0.0:
                self.vel.y *= 0.3

    # ---- 体节跟随（DevourerofGodsBody.cs 257~267） -----------------------
    def _update_segments(self, ticks):
        """BaseWormNPC.ExactSegmentLogic：记录头部走过的路径点，
        体节沿这条路径按固定弧长排布。
        用累计弧长 + 二分查找定位，保证相邻体节的弧长间隔恒等于段间距。"""
        spacing = self.spacing()
        pts = self.path_points
        if not pts or pts[-1].distance(self.c) > 5.0:
            pts.append(self.c.copy())
        if len(pts) > 2400:
            del pts[:len(pts) - 2400]

        n = len(pts)
        cum = [0.0] * n
        for k in range(1, n):
            cum[k] = cum[k - 1] + pts[k - 1].distance(pts[k])
        total = cum[-1]

        tail_dir = V(-math.cos(self.rot - HALF_PI), -math.sin(self.rot - HALF_PI))
        if n > 1:
            d0 = pts[0] - pts[1]
            L0 = d0.length()
            out_dir = V(d0.x / L0, d0.y / L0) if L0 > 1e-6 else tail_dir
            out_rot = (pts[1] - pts[0]).to_rotation() + HALF_PI
        else:
            out_dir = tail_dir
            out_rot = self.rot

        total_seg = len(self.segments)
        for i, s in enumerate(self.segments):
            want = (i + 1) * spacing
            if want > total:
                extra = want - total
                s.c = V(pts[0].x + out_dir.x * extra, pts[0].y + out_dir.y * extra)
                s.rot = out_rot
                continue
            target = total - want
            j = bisect.bisect_left(cum, target)
            if j <= 0:
                s.c = pts[0].copy()
                s.rot = out_rot
                continue
            a = pts[j - 1]
            b = pts[j]
            span = cum[j] - cum[j - 1]
            t = (target - cum[j - 1]) / span if span > 1e-6 else 0.0
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            s.c = V(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
            s.rot = (b - a).to_rotation() + HALF_PI
        tail_n = max(3, total_seg // 12)
        for i, s in enumerate(self.segments):
            s.type = 1 if i >= total_seg - tail_n else 0

    def _update_trail(self):
        self.trail.append(self.c.copy())
        if len(self.trail) > 16:
            self.trail.pop(0)

    def segments_with_head(self):
        yield self.c, self.rot, -1
        for i, s in enumerate(self.segments):
            yield s.c, s.rot, s.type
