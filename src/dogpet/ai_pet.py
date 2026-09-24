"""Chibii Devourer（Q 版神吞宠物）AI。

直译三份源码：
  · Terraria Projectile.AI_026 的 type 319（黑猫）分支——移动、跳跃、动画
  · Calamity ChibiiDoggo.cs——陆地/飞行状态切换、拖尾、黑暗彩蛋
  · Calamity ChibiiDoggoFly.cs——飞行贴图与 12 段拖尾
"""

import math
import random

from . import config as C
from .vec import V, clamp, wrap_angle


class ChibiiPet:
    def __init__(self, world, scale=1.8):
        self.world = world
        self.scale = scale
        self.w = float(C.CHIBII_HITBOX[0])
        self.h = float(C.CHIBII_HITBOX[1])
        self.pos = V(world.origin_x + world.W * 0.5,
                     world.ground_y - self.h * scale)
        self.vel = V()
        self.sprite_direction = 1
        self.frame = C.PET_FRAME_IDLE
        self.frame_counter = 0
        self.tile_collide = True
        self.rotation = 0.0
        self.old_pos = [self.pos.copy() for _ in range(C.TRAIL_FLY_LEN)]
        self.old_rot = [0.0] * C.TRAIL_FLY_LEN
        self.notlocalai1 = 0.0
        self.collide_prev = True
        self.on_ground = False
        self.landed = False
        self.switched = False
        self.anim_speed = C.ANIM_SPEED_SCALE
        self.fly_mode = False
        self.devour_pulse = 0.0
        self.stuck_timer = 0.0
        self.talk_cooldown = 0.0

    # ---- 几何 -----------------------------------------------------------
    @property
    def center(self):
        s = self.scale
        return V(self.pos.x + self.w * s * 0.5, self.pos.y + self.h * s * 0.5)

    def hitbox(self):
        s = self.scale
        return (self.pos.x, self.pos.y, self.w * s, self.h * s)

    # ---- 主更新 ---------------------------------------------------------
    def update(self, target, ticks=1.0):
        self.world.tick()
        ticks = ticks * self.anim_speed
        target_pos = target.pos
        w = self.world

        self.old_pos.insert(0, self.pos.copy())
        self.old_pos.pop()
        self.old_rot.insert(0, self.rotation)
        self.old_rot.pop()

        s = self.scale
        want_center = V(self.pos.x + self.w * s * 0.5, self.pos.y + self.h * s * 0.5)
        dist_target = want_center.distance(target_pos)

        self.fly_mode = self._decide_fly(target_pos, want_center, dist_target)

        if self.fly_mode:
            self._fly_step(target_pos, ticks)
        else:
            self._ground_step(target_pos, ticks)

        self._easter_egg(ticks)

    def _decide_fly(self, tp, center, dist):
        if dist > 260.0:
            return True
        if tp.y < center.y - 70.0:
            return True
        if self.stuck_timer > 40.0:
            return True
        return False

    # ---- 地面：AI_026 逐行直译 ------------------------------------------
    def _ground_step(self, tp, ticks):
        s = self.scale
        v = self.vel
        center_x = self.pos.x + self.w * s * 0.5
        center_y = self.pos.y + self.h * s * 0.5

        dx = tp.x - center_x
        left = dx < -C.PET_DEADZONE
        right = dx > C.PET_DEADZONE

        accel = C.PET_ACCEL * s * ticks
        if left:
            if v.x > -3.5 * s:
                v.x -= accel
            else:
                v.x -= accel * C.PET_TURN_FALLOFF
        elif right:
            if v.x < 3.5 * s:
                v.x += accel
            else:
                v.x += accel * C.PET_TURN_FALLOFF
        else:
            v.x *= C.PET_FRICTION
            if -accel <= v.x <= accel:
                v.x = 0.0

        max_speed = C.PET_MAX_SPEED * s
        if v.x > max_speed:
            v.x = max_speed
        elif v.x < -max_speed:
            v.x = -max_speed

        wall = self._wall_ahead(left, right)
        if self.on_ground and wall:
            self.stuck_timer += ticks
            self._try_jump(left, right)
            if self.stuck_timer > 30.0:
                v.y = min(v.y, -7.0 * s)
        else:
            self.stuck_timer = max(0.0, self.stuck_timer - ticks * 2.0)

        if v.x < 0:
            direction = -1
        elif v.x > 0:
            direction = 1
        else:
            direction = 0
        if direction:
            self.sprite_direction = -direction

        self._move_with_collision(ticks)
        self._animate_ground()

    def _wall_ahead(self, left, right):
        s = self.scale
        w = self.world
        gx = (self.pos.x + self.w * s * 0.5)
        gy = (self.pos.y + self.h * s * 0.5)
        step = 1.0 if right else (-1.0 if left else 0.0)
        probe_x = gx + step * (self.w * s * 0.5 + 3.0) + self.vel.x * 2.0
        return w.solid_at(probe_x, gy)

    def _try_jump(self, left, right):
        s = self.scale
        w = self.world
        if not self.on_ground:
            return
        gx = self.pos.x + self.w * s * 0.5
        gy = self.pos.y + self.h * s * 0.5
        head_y = self.pos.y + 2.0
        step = 1.0 if right else (-1.0 if left else 0.0)
        px = gx + step * (self.w * s * 0.5 + 3.0)
        if not w.solid_at(px, self.pos.y - 8.0) and not w.solid_at(px, self.pos.y - 24.0):
            self.vel.y = -5.1 * s
        elif not w.solid_at(px, self.pos.y - 40.0):
            self.vel.y = -7.1 * s
        elif not w.solid_at(px, self.pos.y - 88.0):
            self.vel.y = -9.1 * s
        else:
            self.vel.y = -11.1 * s
        self.on_ground = False

    def _move_with_collision(self, ticks):
        s = self.scale
        w = self.world
        self.vel.y += C.PET_GRAVITY * s * ticks
        if self.vel.y > C.PET_MAX_FALL * s:
            self.vel.y = C.PET_MAX_FALL * s

        nx = self.pos.x + self.vel.x * ticks
        ny = self.pos.y + self.vel.y * ticks

        feet_x = nx + self.w * s * 0.5
        feet_y = ny + self.h * s
        blocked = w.solid_at(feet_x, feet_y)

        if blocked and self.vel.y >= 0:
            ny = self.pos.y
            self.vel.y = 0.0
            self.on_ground = True
            self.landed = True
        else:
            self.on_ground = False
            self.landed = False

        edge_l = nx
        edge_r = nx + self.w * s
        if w.solid_at(edge_l, ny + self.h * s * 0.5) or w.solid_at(edge_r, ny + self.h * s * 0.5):
            nx = self.pos.x
            self.vel.x = 0.0

        self.pos.x = nx
        self.pos.y = ny
        self.rotation = 0.0

    def _animate_ground(self):
        v = self.vel
        s = self.scale
        flag8 = abs(v.x) < 1e-6
        if 0.0 <= v.y <= C.PET_LAND_VY_MAX * s:
            if flag8:
                self.frame = C.PET_FRAME_IDLE
                self.frame_counter = 0
            elif v.x < -C.PET_WALK_VX_MIN * s or v.x > C.PET_WALK_VX_MIN * s:
                self.frame_counter += int(abs(v.x / s)) + 1
                if self.frame_counter > C.PET_WALK_FRAME_GATE:
                    self.frame += 1
                    self.frame_counter = 0
                if self.frame > C.PET_WALK_RANGE[1]:
                    self.frame = C.PET_WALK_RANGE[0]
                if self.frame < C.PET_WALK_RANGE[0]:
                    self.frame = C.PET_WALK_RANGE[0]
            else:
                self.frame = C.PET_FRAME_IDLE
                self.frame_counter = 0
        else:
            self.frame_counter = 0
            self.frame = C.PET_FRAME_JUMP

    # ---- 飞行：AI_026 的 319 空中分支 ------------------------------------
    def _fly_step(self, tp, ticks):
        s = self.scale
        v = self.vel
        c = self.center
        d = tp - V(c.x, c.y - 40.0 * s)
        dist = d.length()
        if dist > 1.0:
            desired = d.normalized() * min(C.PET_MAX_SPEED * 2.4 * s, dist * 0.12)
        else:
            desired = V()
        k = 0.14 * ticks
        v.x += (desired.x - v.x) * k
        v.y += (desired.y - v.y) * k

        self.pos.x += v.x * ticks
        self.pos.y += v.y * ticks

        self.rotation = v.x * C.PET_FLY_ROT_FACTOR * (1.0 if self.sprite_direction >= 0 else -1.0)
        if self.rotation > 1.2:
            self.rotation = 1.2
        elif self.rotation < -1.2:
            self.rotation = -1.2

        if v.x < -0.35:
            self.sprite_direction = -1
        elif v.x > 0.35:
            self.sprite_direction = 1

        self.frame_counter += ticks
        while self.frame_counter >= C.PET_FLY_FRAME_GATE:
            self.frame_counter -= C.PET_FLY_FRAME_GATE
            self.frame += 1
        if self.frame > C.PET_FLY_RANGE[1]:
            self.frame = C.PET_FLY_RANGE[0]
        if self.frame < C.PET_FLY_RANGE[0]:
            self.frame = C.PET_FLY_RANGE[0]

        w = self.world
        s2 = self.scale
        if self.pos.x < w.origin_x - 30:
            self.pos.x = w.origin_x - 30
            v.x = abs(v.x)
        if self.pos.x + self.w * s2 > w.origin_x + w.W + 30:
            self.pos.x = w.origin_x + w.W + 30 - self.w * s2
            v.x = -abs(v.x)
        if self.pos.y < w.origin_y - 30:
            self.pos.y = w.origin_y - 30
            v.y = abs(v.y)
        if self.pos.y + self.h * s2 > w.ground_y + 10:
            self.pos.y = w.ground_y + 10 - self.h * s2
            v.y = -abs(v.y)
            self.on_ground = True
        else:
            self.on_ground = False

    # ---- 黑暗彩蛋（ChibiiDoggo.cs AI 段） --------------------------------
    def _easter_egg(self, ticks):
        self.talk_cooldown = max(0.0, self.talk_cooldown - ticks)
        self.notlocalai1 += 1.0 if self.fly_mode else -0.0
        self.notlocalai1 = clamp(self.notlocalai1, C.EASTER_DARK_MIN,
                                 C.EASTER_DARK_MAX)
        if self.talk_cooldown <= 0:
            self.talk_cooldown = random.uniform(900, 2400)
            self.notlocalai1 = clamp(self.notlocalai1, -3600.0, 120.0)
            return random.choice((None, None, None, "meow", "scream"))

    def frame_pixmap_index(self, lib):
        frames = lib.fly if self.fly_mode else lib.chibii
        return frames[min(max(self.frame, 0), len(frames) - 1)]

    def trail_pixmaps(self, lib):
        frames = lib.fly_mono if self.fly_mode else lib.chibii_mono
        return frames[min(max(self.frame, 0), len(frames) - 1)]
