"""桌宠运行时：透明置顶窗口、60FPS 主循环、两种形态渲染、托盘交互。"""

import ctypes
import json
import math
import os
import random
import sys
import time
import traceback

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor, QGuiApplication,
                           QIcon, QPainter, QPen, QPixmap, QRegion)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QDialog,
                               QGroupBox, QHBoxLayout, QLabel, QMenu, QPushButton,
                               QRadioButton, QSlider, QSystemTrayIcon, QVBoxLayout,
                               QWidget)

from . import assets, config as C, fx
from .ai_pet import ChibiiPet
from .ai_worm import DoGWorm
from .modes import ModeEngine
from .music import MusicPlayer
from .vec import V, HALF_PI
from .world import World

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080

STAR_COLORS = ((255, 226, 140), (255, 168, 96), (168, 232, 255))


def settings_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "DoGPet")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "settings.json")


SOUND_FILES = {
    "laugh": ("DoGLaugh.ogg", 0.45),
    "laser": ("DogmaLasersFire.ogg", 0.55),
    "spawn": ("dog_spawn.ogg", 0.62),
    "teleport": ("dog_teleport.ogg", 0.55),
    "wall_spawn": ("dog_laserwall_spawn.ogg", 0.62),
    "wall_fire": ("dog_laserwall_fire.ogg", 0.78),
    "hurt": ("dog_hurt.ogg", 0.62),
    "jump": ("dog_jump.ogg", 0.50),
    "seg1": ("dog_seg1.ogg", 0.48),
    "seg2": ("dog_seg2.ogg", 0.48),
    "seg3": ("dog_seg3.ogg", 0.48),
    "seg4": ("dog_seg4.ogg", 0.48),
    "beam": ("dog_beam.ogg", 0.55),
    "death": ("dog_death.ogg", 0.60),
}


class PetWindow(QWidget):
    def __init__(self, world):
        super().__init__(None)
        self.world = world
        self.lib = assets.library()
        self.setWindowTitle(C.APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMouseTracking(True)

        self.settings = load_settings()
        self.scale_chibii = float(self.settings.get("scale_chibii", 3.0))
        self.scale_dog = float(self.settings.get("scale_dog", C.DOG_DEFAULT_SCALE))
        self.form = self.settings.get("form", C.FORM_DOG)
        self.mode = self.settings.get("mode", C.MODE_FOLLOW)
        self.sound_on = bool(self.settings.get("sound", True))
        self.anim_speed = float(self.settings.get("anim_speed", 1.0))
        self.use_windows = bool(self.settings.get("use_windows", True))
        self.show_ball = bool(self.settings.get("show_ball", True))
        self.heart_target = bool(self.settings.get("heart_target", False))

        self.world.use_windows = self.use_windows
        self.engine = ModeEngine(self.world, self.mode,
                                 "heart" if self.heart_target else "mouse")
        self.particles = fx.Particles()
        self.heart = fx.Heart(self.world)
        self._heart_off = None
        self.music = MusicPlayer(self)
        self.portals = []
        self.laser_walls = []
        self._laser_spawned = False
        self._bite_cd = 0.0
        self._bite_flash = 0.0
        self._charging = False
        self._off_timer = 0.0
        self.pet = None
        self.module = None

        self._click_through = None
        self._hover_pet = False
        self._drag_off = None
        self._last = time.perf_counter()
        self._fps = 0.0
        self._fps_acc = 0.0
        self._fps_n = 0
        self._sound_pool = {}
        self._snd_ready = False
        self._talk_timer = random.uniform(600, 1800)
        self._laser_phase = 0.0
        self._box = None
        self._dirty_prev = None
        self._acc = 0.0
        self._screen_rect = QRect(int(self.world.origin_x), int(self.world.origin_y),
                                  int(self.world.W), int(self.world.H))
        self._geo = QRect(self._screen_rect.center().x() - 120,
                          self._screen_rect.center().y() - 120, 240, 240)
        self.setGeometry(self._geo)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(C.RENDER_MS)
        self._timer.timeout.connect(self._loop)
        self._timer.start()

        self._input_timer = QTimer(self)
        self._input_timer.setInterval(40)
        self._input_timer.timeout.connect(self._poll_cursor)
        self._input_timer.start()

        self._ensure_form()
        self.set_click_through(True)
        QTimer.singleShot(220, self._portal_enter)

    # ---- 模块 ------------------------------------------------------------
    def load_module(self, module):
        """卸载当前宠物，挂上新模块。module 为 modkit.PetModule。"""
        if self.pet is not None:
            try:
                hook = getattr(self.pet, "detach", None)
                if hook is not None:
                    hook()
            except Exception:
                traceback.print_exc()
            self.pet = None
        self.module = module
        self.settings["module"] = module.id
        self.particles.clear()
        self.portals.clear()
        self.laser_walls.clear()
        self._dirty_prev = None
        try:
            self.pet = module.create(self)
        except Exception:
            traceback.print_exc()
            self.pet = None
        self.force_repaint()
        return self.pet

    # ---- 形态 ------------------------------------------------------------
    def _ensure_form(self):
        """没有加载模块时，默认挂上自带的「神明吞噬者」。"""
        if self.pet is not None:
            return
        try:
            import modkit
            want = self.settings.get("module", "devourer_of_gods")
            mod = modkit.find(want) or (modkit.scan() or [None])[0]
            if mod is not None:
                self.load_module(mod)
        except Exception:
            traceback.print_exc()

    def set_form(self, form):
        """形态交给模块决定（模块自己知道有哪些形态）。"""
        self.form = form
        self.settings["form"] = form
        if self.pet is not None and hasattr(self.pet, "set_form"):
            self.pet.set_form(form)
        self.save_settings()
        self.force_repaint()

    def set_mode(self, mode):
        self.mode = mode
        self.engine.set_mode(mode)
        self.save_settings()
        if self.form == C.FORM_DOG and mode == C.MODE_SKY:
            self._portal_enter()
        else:
            self.force_repaint()

    def set_scale(self, form, value):
        if form == C.FORM_CHIBII:
            self.scale_chibii = value
        else:
            self.scale_dog = value
        if self.pet is not None and hasattr(self.pet, "set_scale"):
            self.pet.set_scale(form, value)
        self.save_settings()

    def set_sound(self, on):
        self.sound_on = on
        self.save_settings()

    def set_anim_speed(self, v):
        self.anim_speed = v
        if self.pet is not None and hasattr(self.pet, "chibii") and self.pet.chibii:
            self.pet.chibii.anim_speed = v
        self.save_settings()

    def set_use_windows(self, on):
        self.use_windows = on
        self.world.use_windows = on
        self.save_settings()

    def save_settings(self):
        data = dict(self.settings)
        data.update({
            "form": self.form,
            "mode": self.mode,
            "scale_chibii": self.scale_chibii,
            "scale_dog": self.scale_dog,
            "sound": self.sound_on,
            "anim_speed": self.anim_speed,
            "use_windows": self.use_windows,
            "show_ball": self.show_ball,
            "heart_target": self.heart_target,
        })
        self.settings = data
        try:
            with open(settings_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def set_show_ball(self, on):
        self.show_ball = bool(on)
        ball = getattr(self, "_ball", None)
        if ball is not None:
            ball.setVisible(self.show_ball)
        self.save_settings()

    def set_heart_target(self, on):
        """切换追踪目标：True = 决心红心，False = 鼠标。"""
        self.heart_target = bool(on)
        self.engine.set_target_source("heart" if self.heart_target else "mouse")
        self.settings["heart_target"] = self.heart_target
        self._dirty_prev = None
        self.save_settings()
        self.force_repaint()

    def play_music(self, idx):
        return self.music.play_index(idx)

    def stop_music(self):
        self.music.stop()

    def recenter(self):
        if self.pet is not None and hasattr(self.pet, "recenter"):
            self.pet.recenter()
        else:
            self.force_repaint()

    def open_settings(self, app):
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return
        dlg = SettingsDialog(self, app)
        dlg.finished.connect(lambda _=0: setattr(self, "_settings_dlg", None))
        self._settings_dlg = dlg
        scr = self.world.work
        dlg.move(int(scr.center().x() - dlg.width() / 2),
                 int(scr.center().y() - dlg.height() / 2))
        dlg.show()

    # ---- 音效 ------------------------------------------------------------
    def _make_player(self, key):
        spec = SOUND_FILES.get(key)
        if spec is None:
            return None
        name, vol = spec
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception:
            self._snd_ready = True
            return None
        p = assets.path("sfx", name)
        if not os.path.exists(p):
            return None
        out = QAudioOutput(self)
        out.setVolume(vol)
        pl = QMediaPlayer(self)
        pl.setAudioOutput(out)
        pl.setSource(QUrl.fromLocalFile(p))
        return pl

    def _play(self, key):
        """懒加载音效：第一次播到才建 player。

        QSoundEffect 解不了这些 ogg（会静默失败），所以一律走 QMediaPlayer。
        """
        if not self.sound_on:
            return
        pl = self._sound_pool.get(key)
        if pl is None:
            pl = self._make_player(key)
            if pl is None:
                return
            self._sound_pool[key] = pl
        pl.stop()
        pl.setPosition(0)
        pl.play()

    # 模块通过 host.play(key) 调音效
    play = _play

    def _warm_sounds(self):
        for k in ("spawn", "teleport", "wall_spawn", "wall_fire", "hurt", "jump"):
            if k not in self._sound_pool:
                pl = self._make_player(k)
                if pl is not None:
                    self._sound_pool[k] = pl

    # ---- 输入 / 穿透 -----------------------------------------------------
    def _poll_cursor(self):
        p = QCursor.pos()
        local = self.mapFromGlobal(p)
        inside = False
        for b in self._pet_boxes():
            if b.contains(QPointF(local)):
                inside = True
                break
        self._hover_pet = inside
        self.set_click_through(not inside and self._drag_off is None)

    def set_click_through(self, on):
        if self._click_through == on:
            return
        self._click_through = on
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if on:
                ex |= WS_EX_TRANSPARENT | WS_EX_LAYERED
            else:
                ex &= ~WS_EX_TRANSPARENT
                ex |= WS_EX_LAYERED
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        except Exception:
            pass

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        g = e.globalPosition()
        local = self.mapFromGlobal(g.toPoint())
        on_pet = any(b.contains(QPointF(local)) for b in self._pet_boxes())
        if on_pet:
            pos = self._pet_screen_pos()
            self._drag_off = (g.x() - pos.x, g.y() - pos.y)
            e.accept()
            return
        if self.engine.target_source == "heart":
            # 目标模式下：屏幕任意位置按住就能牵引决心
            self.heart.dragging = True
            self.heart.cursor = V(g.x(), g.y())
            e.accept()
            return
        self._drag_off = None

    def mouseMoveEvent(self, e):
        g = e.globalPosition()
        if self.heart.dragging:
            self.heart.cursor = V(g.x(), g.y())
            e.accept()
            return
        if self._drag_off is not None:
            self._place_pet(g.x() - self._drag_off[0], g.y() - self._drag_off[1])
            e.accept()

    def mouseReleaseEvent(self, e):
        if self.heart.dragging:
            self.heart.dragging = False
        self._drag_off = None
        self._poll_cursor()

    def _pet_screen_pos(self):
        if self.pet is not None and hasattr(self.pet, "pet_position"):
            return self.pet.pet_position()
        return V(self._geo.x(), self._geo.y())

    def _place_pet(self, gx, gy):
        if self.pet is not None and hasattr(self.pet, "place"):
            self.pet.place(gx, gy)

    # ---- 主循环 ----------------------------------------------------------
    def _loop(self):
        now = time.perf_counter()
        dt = now - self._last
        self._last = now
        if dt > 0.25:
            dt = 0.25
        self._acc += dt
        step = 1.0 / C.PET_TICK_HZ
        n = 0
        while self._acc >= step and n < 4:
            self.physics(1.0)
            self._acc -= step
            n += 1
        if self._acc > step * 4.0:
            self._acc = 0.0
        if n == 0:
            return
        if dt > 0:
            self._fps_acc += 1.0 / dt
            self._fps_n += 1
            if self._fps_n >= 30:
                self._fps = self._fps_acc / self._fps_n
                self._fps_acc = 0.0
                self._fps_n = 0
        self._update_window()

    def physics(self, ticks):
        """固定步长推进（1 tick）——保证与原版 60 ticks/s 完全一致，消除抖动。"""
        if self.engine.target_source == "heart":
            self.heart.update(ticks)
        self.engine.update(ticks, self.heart)
        self.particles.update(ticks)
        if self.portals:
            for pt in self.portals:
                pt.update(ticks)
            self.portals = [pt for pt in self.portals if not pt.done]
        if self.laser_walls:
            tp = self.engine.target.pos
            for lw in self.laser_walls:
                lw.update(ticks, tp)
                if lw.fired:
                    lw.fired = False
                    self._play("wall_fire")
            self.laser_walls = [lw for lw in self.laser_walls if not lw.dead]
        if self.pet is not None:
            self.pet.update(ticks)
            hook = getattr(self.pet, "tick_world", None)
            if hook is not None:
                hook(ticks)
        self._bite_flash = max(0.0, getattr(self, "_bite_flash", 0.0) - ticks)

    def step(self, ticks):
        self.physics(ticks)
        self._update_window()

    def _update_window(self):
        """窗口贴合内容包围盒，但只在必要时改几何，避免每帧 SetWindowPos。"""
        reg = self._content_region_global()
        need = reg.boundingRect().adjusted(-12, -12, 12, 12)
        if need.width() < C.WINDOW_MIN_SIZE[0]:
            cx = need.center().x()
            need.setLeft(int(cx - C.WINDOW_MIN_SIZE[0] / 2))
            need.setRight(need.left() + C.WINDOW_MIN_SIZE[0])
        if need.height() < C.WINDOW_MIN_SIZE[1]:
            cy = need.center().y()
            need.setTop(int(cy - C.WINDOW_MIN_SIZE[1] / 2))
            need.setBottom(need.top() + C.WINDOW_MIN_SIZE[1])
        need = need.intersected(self._screen_rect)
        if need.isEmpty():
            return

        cur = self._geo
        fits = cur.contains(need)
        # 几何只在内容真的装不下时才扩，几乎不主动收缩——每帧 SetWindowPos+全窗重绘会卡顿
        too_big = (cur.width() * cur.height()) > (need.width() * need.height()) * 7.0
        if not fits or too_big:
            grown = need.adjusted(-need.width() // 6, -need.height() // 6,
                                  need.width() // 6, need.height() // 6)
            self._geo = grown.intersected(self._screen_rect)
            self._dirty_prev = None
            self.setGeometry(self._geo)
            self.update()
            return

        local = reg.translated(-cur.x(), -cur.y())
        prev = self._dirty_prev
        if prev is not None and not prev.isEmpty():
            local = local.united(prev)
        self._dirty_prev = reg.translated(-cur.x(), -cur.y())
        self.update(local)

    def force_repaint(self):
        self._dirty_prev = None
        self.update()

    def _content_aabb(self):
        """Q版：包围盒必须包住全部拖尾历史位置与粒子，否则会留残影。"""
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

    def _content_region_global(self):
        """返回全局坐标的脏区 region：由当前模块自己算。"""
        if self.pet is not None:
            try:
                box = self.pet.bounds()
                if box is not None and not box.isEmpty():
                    return box
            except Exception:
                traceback.print_exc()
        if self.form == C.FORM_CHIBII:
            return QRegion(self._content_aabb().toAlignedRect())
        wm = self.worm
        if wm is None:
            return QRegion(self.world.work)
        s = wm.scale
        sizecache = {}
        rects = []
        ox, oy = self.world.origin_x, self.world.origin_y
        view = QRectF(ox - 400, oy - 400, self.world.W + 800, self.world.H + 800)
        for c, rot, kind in wm.segments_with_head():
            if kind not in sizecache:
                pm = self._dog_pixmap(kind)
                sizecache[kind] = (pm.width() if pm else 0, pm.height() if pm else 0)
            pw, ph = sizecache[kind]
            if pw == 0:
                continue
            if not view.contains(QPointF(c.x, c.y)):
                continue
            # 头部额外覆盖 radial_glow 光晕；其余体节只需覆盖自身与慢速粒子
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
        if self.engine.mode == C.MODE_DEVOUR:
            for st in self.engine.stars:
                reg = reg.united(QRegion(QRect(int(st.pos.x - 46), int(st.pos.y - 46), 92, 92)))
        for pt in self.portals:
            rr = 240.0
            reg = reg.united(QRegion(QRect(int(pt.x - rr), int(pt.y - rr),
                                           int(rr * 2), int(rr * 2))))
        if self.engine.target_source == "heart":
            reg = reg.united(QRegion(self.heart.bounds()))
        if self.laser_walls:
            # 激光网横跨全屏，直接整屏重绘
            return QRegion(self.rect())
        if reg.isEmpty():
            reg = QRegion(self._head_rect_global())
        return reg

    def _head_rect_global(self):
        wm = self.worm
        if wm is None:
            return self.world.work
        pm = self._dog_pixmap(-1)
        s = wm.scale
        hw = (pm.width() * s * 0.5 + 120) if pm is not None else 150
        hh = (pm.height() * s * 0.5 + 120) if pm is not None else 150
        return QRect(int(wm.c.x - hw), int(wm.c.y - hh), int(hw * 2), int(hh * 2))

    def _pet_boxes(self):
        ox, oy = self._geo.x(), self._geo.y()
        if self.pet is not None and hasattr(self.pet, "render_box"):
            x, y, w, h = self.pet.render_box()
            return [QRectF(x - ox, y - oy, w, h)]
        return [QRectF(0, 0, 10, 10)]

    def worm_render_box(self):
        if self.worm is None:
            return (0.0, 0.0, 10.0, 10.0)
        s = self.worm.scale
        sizes = []
        for c, rot, kind in self.worm.segments_with_head():
            pm = self._dog_pixmap(kind)
            if pm is None:
                continue
            sizes.append((c.x, c.y, pm.width() * s, pm.height() * s))
        if not sizes:
            return (0.0, 0.0, 10.0, 10.0)
        x0 = min(s_[0] - s_[2] / 2 for s_ in sizes)
        y0 = min(s_[1] - s_[3] / 2 for s_ in sizes)
        x1 = max(s_[0] + s_[2] / 2 for s_ in sizes)
        y1 = max(s_[1] + s_[3] / 2 for s_ in sizes)
        return (x0, y0, x1 - x0, y1 - y0)

    def _step_chibii(self, ticks):
        pet = self.chibii
        was_fly = pet.fly_mode
        pet.update(self.engine.target, ticks)
        if was_fly != pet.fly_mode:
            cx, cy = pet.center.x, pet.center.y
            self.particles.burst_switch(cx, cy, C.STATE_SWITCH_DUST)
        if pet.fly_mode:
            self.particles.trail_dust(pet.center.x, pet.center.y,
                                      -pet.vel.x * 0.5, -pet.vel.y * 0.5, 1)
        elif pet.on_ground and abs(pet.vel.x) > 1.0:
            self.particles.trail_dust(pet.center.x, pet.center.y + pet.h * pet.scale * 0.4,
                                      0, 0, 1)

        self._talk_timer -= ticks
        if self._talk_timer <= 0:
            self._talk_timer = random.uniform(700, 1900)
            self._play(random.choice(("laugh", "hurt", "jump", "seg1")))

        e = self.engine
        if e.mode == C.MODE_DEVOUR:
            got = e.consume(pet.center, 26.0 * pet.scale)
            if got:
                self.particles.spawn(pet.center.x, pet.center.y, 22,
                                     speed=4.5, size=3.0, life=40,
                                     palette=fx.DUST_DEVOUR)
                r = pet.scale * random.uniform(1.02, 1.06)
                pet.scale = min(r, self.scale_chibii * 1.7)

    def _step_worm(self, ticks):
        wm = self.worm
        e = self.engine
        if e.mode == C.MODE_DEVOUR:
            got = e.consume(wm.c, 34.0 * wm.scale)
            if got:
                self.particles.spawn(wm.c.x, wm.c.y, 30, speed=6.0, size=3.4,
                                     life=46, palette=fx.DUST_DEVOUR)
                self._play("death")
                wm.count = min(wm.count + got, 64)
                while len(wm.segments) < wm.count:
                    wm.segments.append(type(wm.segments[0])(wm.c.x, wm.c.y))
                    wm.count = len(wm.segments)
        wm.update(e.target, ticks,
                  wander=(e.mode in (C.MODE_FOLLOW, C.MODE_SKY)))
        self._laser_phase += ticks

        if wm.charge_timer > 0 and not self._charging:
            self._charging = True
            self._play("jump")
            self.particles.spawn(wm.c.x, wm.c.y, 24, speed=7.0, size=3.6,
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
                self.particles.trail_dust(seg.c.x, seg.c.y, 0, 0, 1)

        if wm.state == 2 and random.random() < 0.02:
            self._play("beam")
        if wm.charge_timer > 0 and random.random() < 0.35:
            self.particles.spawn(wm.c.x, wm.c.y, 3, speed=2.4, size=3.2, life=26,
                                 palette=fx.DUST_GLOW)

    def _draw_portals(self, p):
        if not self.portals:
            return
        pm = self.lib.portal
        if pm is None or pm.isNull():
            return
        for pt in self.portals:
            alpha, open_k = pt.phase()
            if alpha <= 0.01:
                continue
            sc = pt.scale
            w = max(pm.width() * sc * (0.06 + 0.94 * open_k), 2.0)
            h = pm.height() * sc * (0.45 + 0.55 * open_k)
            fx.radial_glow(p, pt.x, pt.y, h * 0.62, (168, 110, 255), int(160 * alpha))
            p.save()
            p.translate(pt.x, pt.y)
            p.rotate(math.degrees(pt.angle))
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setOpacity(alpha * (0.78 + 0.22 * math.sin(pt.spin * 3.1)))
            p.drawPixmap(QRectF(-w / 2, -h / 2, w, h), pm,
                         QRectF(0, 0, pm.width(), pm.height()))
            p.restore()
            p.save()
            p.translate(pt.x, pt.y)
            p.rotate(math.degrees(pt.spin * 1.6))
            p.setPen(QPen(QColor(206, 164, 255, int(170 * alpha)), 2.0))
            p.setBrush(Qt.NoBrush)
            rr = h * 0.30
            p.drawEllipse(QRectF(-rr, -rr * 0.34, rr * 2.0, rr * 0.68))
            p.restore()

    def spawn_portal(self, x, y, angle=0.0):
        sc = 0.6
        wm = getattr(self.pet, "worm", None) if self.pet is not None else None
        ch = getattr(self.pet, "chibii", None) if self.pet is not None else None
        if wm is not None:
            sc = wm.scale * 0.34
        elif ch is not None:
            sc = ch.scale * 0.34
        sc = max(sc, 0.14)
        self.portals.append(fx.Portal(x, y, angle, sc))
        if len(self.portals) > 6:
            self.portals.pop(0)
        self.particles.spawn(x, y, 34, speed=5.5, size=3.4, life=44,
                             palette=fx.DUST_GLOW)

    def _portal_enter(self, x=None, y=None):
        """开场演出交给模块自己决定（神吞模块会开门走出来）。"""
        if self.pet is not None and hasattr(self.pet, "recenter"):
            self.pet.recenter()
        else:
            self.force_repaint()

    def _check_mouse_bite(self, ticks):
        """神吞咬到鼠标：在鼠标位置播官方受击音效并爆粒子。"""
        self._bite_cd -= ticks
        if self._bite_cd > 0:
            return
        tp = self.engine.target.pos
        if self.form == C.FORM_DOG and self.worm:
            head = self.worm.c
            reach = 56.0 * self.worm.scale
        else:
            head = self.chibii.center
            reach = 38.0 * self.chibii.scale
        if head.distance(tp) > reach:
            return
        self._bite_cd = 58.0
        self._play("hurt")
        self._play(random.choice(("seg1", "seg2", "seg3", "seg4")))
        self.particles.spawn(tp.x, tp.y, 20, speed=4.8, size=3.2, life=34,
                             palette=fx.DUST_DEVOUR)
        self._bite_flash = 12.0

    def _check_offscreen(self, ticks):
        """只有头部自己跑到屏幕外太久，才开门把它送回来。"""
        if self.form != C.FORM_DOG or not self.worm:
            return
        w = self.world
        hx, hy = self.worm.c.x, self.worm.c.y
        margin = 430.0
        inside = (w.origin_x - margin < hx < w.origin_x + w.W + margin and
                  w.origin_y - margin < hy < w.ground_y + margin)
        if inside:
            self._off_timer = 0.0
            return
        self._off_timer += ticks
        if self._off_timer > 700.0:
            self._off_timer = 0.0
            self._portal_enter()

    def _spawn_laser_wall(self, wm):
        """官方 DoGLaserWalls：间距 250、速度 0.5、六种阵型随机。"""
        s = wm.scale
        lw = fx.LaserWall(wm.c.x, wm.c.y,
                          attack_speed=0.5,
                          laser_dist=250.0 * s,
                          laser_type=random.randint(0, 5),
                          target=V(wm.c.x, wm.c.y))
        self.laser_walls.append(lw)
        if len(self.laser_walls) > 4:
            self.laser_walls.pop(0)
        self._play("wall_spawn")

    def _draw_laser_walls(self, p):
        for lw in self.laser_walls:
            if lw.laser_fx <= 0.001:
                continue
            f = min(lw.laser_fx, 1.0)
            opacity = (0.65 if lw.done else 0.30) * f * f
            col = lw.draw_color
            thick = 0.03 * (lw.laser_fx if lw.laser_fx > 1.0 else f * f)
            thick *= fx.remap(lw.sine, -1.0, 1.0, 0.8, 1.1)
            base = max(thick * 900.0 * lw.laser_dist / 250.0, 1.0)
            for (x0, y0, x1, y1, cross) in lw.beams():
                if lw.done:
                    p.setPen(QPen(QColor(0, 0, 0, int(150 * opacity)), base * 3.2))
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                    p.setPen(QPen(QColor(col[0], col[1], col[2], int(230 * opacity)),
                                  base * 2.0))
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                    p.setPen(QPen(QColor(255, 255, 255, int(240 * opacity)), base * 0.85))
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                else:
                    p.setPen(QPen(QColor(col[0], col[1], col[2], int(170 * opacity)),
                                  max(base * 0.7, 1.2)))
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    # ---- 绘制 ------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(event.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        ox, oy = self._geo.x(), self._geo.y()
        p.translate(-ox, -oy)

        self._draw_portals(p)
        self._draw_stars(p)
        if self.engine.target_source == "heart":
            self.heart.draw(p)
        self._draw_laser_walls(p)
        if self.pet is not None:
            try:
                self.pet.draw(p, self)
            except Exception:
                traceback.print_exc()
        self.particles.draw(p)
        p.end()

    def _draw_stars(self, p):
        e = self.engine
        if e.mode != C.MODE_DEVOUR:
            return
        for st in e.stars:
            col = STAR_COLORS[st.hue]
            pulse = 0.75 + 0.25 * math.sin(self._laser_phase * 0.12 + st.pos.x)
            fx.radial_glow(p, st.pos.x, st.pos.y, st.radius * 3.2 * pulse, col, 130)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(col[0], col[1], col[2], 235))
            r = st.radius * 0.55 * pulse
            p.drawEllipse(QPointF(st.pos.x, st.pos.y), r, r)

    def _draw_chibii(self, p):
        pet = self.chibii
        lib = self.lib
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
            px = op.x + pet.w * s * 0.5
            py = op.y + pet.h * s * 0.5
            p.save()
            p.setOpacity(min(0.85, a * 3.4))
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            self._blit(p, mono, px, py, dw, dh, pet.old_rot[i], pet.sprite_direction)
            p.restore()

        if pet.fly_mode:
            fx.radial_glow(p, cx, cy, dw * 0.85, (150, 108, 255), 70)
        self._blit(p, pm, cx, cy, dw, dh, pet.rotation, pet.sprite_direction)

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
        parts = self.lib.dog_p1 if not (self.worm and self.worm.phase2) else self.lib.dog_p2
        if kind == -1:
            return parts.get("head")
        if kind == 1:
            return parts.get("tail")
        return parts.get("body")

    def _draw_worm(self, p):
        wm = self.worm
        if wm is None:
            return
        s = wm.scale
        parts = self.lib.dog_p2 if wm.phase2 else self.lib.dog_p1
        head = parts.get("head")
        body = parts.get("body")
        tail = parts.get("tail")
        glow_col = (196, 128, 255) if wm.state != 1 else (255, 96, 180)

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
            self._draw_laser(p, wm)
        if wm.charge_timer > 0:
            fx.radial_glow(p, wm.c.x, wm.c.y, 90 * s + 30, (255, 120, 200), 90)

    def _draw_laser(self, p, wm):
        target = self.engine.target.pos
        t = self._laser_phase
        n = 8
        for i in range(n):
            ang = (i / n) * math.tau + t * 0.012
            x0 = target.x + math.cos(ang) * 120.0
            y0 = target.y + math.sin(ang) * 120.0
            x1 = target.x + math.cos(ang) * 900.0
            y1 = target.y + math.sin(ang) * 900.0
            fx.laser(p, x0, y0, x1, y1, 1.6)

    # ---- 交互菜单 --------------------------------------------------------
    def context_menu(self):
        m = QMenu()
        head = m.addMenu("形态")
        g1 = QActionGroup(head)
        for key, label in C.FORM_LABELS.items():
            a = head.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.form == key)
            g1.addAction(a)
            a.triggered.connect(lambda _=False, k=key: self.set_form(k))
        head2 = m.addMenu("模式")
        g2 = QActionGroup(head2)
        for key, label in C.MODE_LABELS.items():
            a = head2.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.mode == key)
            g2.addAction(a)
            a.triggered.connect(lambda _=False, k=key: self.set_mode(k))
        size = m.addMenu("大小")
        for label, val in C.SIZE_OPTIONS[self.form]:
            a = size.addAction(label)
            a.setCheckable(True)
            a.setChecked(abs((self.scale_chibii if self.form == C.FORM_CHIBII
                              else self.scale_dog) - val) < 0.01)
            a.triggered.connect(lambda _=False, v=val: self.set_scale(self.form, v))
        spd = m.addMenu("动画速度")
        g3 = QActionGroup(spd)
        for label, val in C.ANIM_OPTIONS:
            a = spd.addAction(label)
            a.setCheckable(True)
            a.setChecked(abs(self.anim_speed - val) < 0.01)
            g3.addAction(a)
            a.triggered.connect(lambda _=False, v=val: self.set_anim_speed(v))
        a = m.addAction("音效")
        a.setCheckable(True)
        a.setChecked(self.sound_on)
        a.triggered.connect(lambda _=False: self.set_sound(not self.sound_on))
        a = m.addAction("窗口碰撞（踩窗口/撞窗起跳）")
        a.setCheckable(True)
        a.setChecked(self.use_windows)
        a.triggered.connect(lambda _=False: self.set_use_windows(not self.use_windows))
        m.addSeparator()
        a = m.addAction(f"帧率 {self._fps:.0f} FPS")
        a.setEnabled(False)
        return m

    def _apply_scale(self, form, val):
        self.set_scale(form, val)

    def contextMenuEvent(self, e):
        self.context_menu().exec(e.globalPos())


def save_settings(data):
    """把一份设置写回磁盘（启动器也用它保存"目标"选项）。"""
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def load_settings():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


MODE_COLORS = {
    C.MODE_FOLLOW: (120, 228, 255),
    C.MODE_HUNT: (255, 108, 148),
    C.MODE_SKY: (168, 140, 255),
    C.MODE_DEVOUR: (255, 206, 120),
}


SETTINGS_QSS = """
QDialog { background: #17102a; }
QLabel { color: #d8ccf0; font-size: 12px; }
QLabel#stat { color: #9c86d8; font-size: 11px; }
QGroupBox {
    color: #b9a3ff; border: 1px solid #3a2b5c; border-radius: 9px;
    margin-top: 14px; padding: 14px 12px 10px 12px; font-size: 12px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QRadioButton, QCheckBox { color: #e2d8ff; padding: 4px 2px; font-size: 12px; }
QRadioButton::indicator, QCheckBox::indicator { width: 15px; height: 15px; }
QRadioButton::indicator:unchecked { border: 2px solid #5b4788; border-radius: 8px; background: #221838; }
QRadioButton::indicator:checked { border: 2px solid #a878ff; border-radius: 8px; background: #a878ff; }
QCheckBox::indicator:unchecked { border: 2px solid #5b4788; border-radius: 4px; background: #221838; }
QCheckBox::indicator:checked { border: 2px solid #a878ff; border-radius: 4px; background: #a878ff; }
QSlider::groove:horizontal { height: 6px; background: #2c1f45; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #7a56c8; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 14px; margin: -5px 0; border-radius: 7px;
    background: #b78cff; border: 1px solid #d6bcff;
}
QPushButton {
    background: #2c1f45; color: #ece4ff; border: 1px solid #4a3570;
    border-radius: 7px; padding: 7px 16px; font-size: 12px;
}
QPushButton:hover { background: #3b2a60; border-color: #7a5cb8; }
QPushButton:pressed { background: #241a3c; }
"""


class SettingsDialog(QDialog):
    """设置面板：所有改动立刻生效，不用点确定。"""

    def __init__(self, win, app):
        super().__init__(None)
        self.win = win
        self.app = app
        self.setWindowTitle("神吞桌宠 · 设置")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint |
                            Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        self.setStyleSheet(SETTINGS_QSS)
        self.setMinimumWidth(430)
        self._building = True
        self._build()
        self._building = False
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._refresh_stat)
        self._timer.start()
        scr = QGuiApplication.primaryScreen().availableGeometry()
        max_h = int(scr.height() * 0.86)
        self.setMinimumWidth(452)
        self.setMaximumHeight(max_h)
        self.resize(452, max_h)

    def _build(self):
        from PySide6.QtWidgets import QScrollArea
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent")
        root = QVBoxLayout(inner)
        root.setSpacing(10)
        root.setContentsMargins(16, 10, 16, 14)

        g = QGroupBox("形态")
        gl = QVBoxLayout(g)
        self.form_btns = QButtonGroup(self)
        for key, label in C.FORM_LABELS.items():
            rb = QRadioButton(label)
            rb.setChecked(self.win.form == key)
            self.form_btns.addButton(rb)
            rb.toggled.connect(lambda on, k=key: self._pick_form(on, k))
            gl.addWidget(rb)
        root.addWidget(g)

        g = QGroupBox("模式")
        gl = QVBoxLayout(g)
        self.mode_btns = QButtonGroup(self)
        for key, label in C.MODE_LABELS.items():
            rb = QRadioButton(label)
            rb.setChecked(self.win.mode == key)
            self.mode_btns.addButton(rb)
            rb.toggled.connect(lambda on, k=key: self._pick_mode(on, k))
            gl.addWidget(rb)
        root.addWidget(g)

        g = QGroupBox("大小")
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(5, 60)
        self.size_slider.setValue(int(self._cur_mult() * 10))
        self.size_slider.valueChanged.connect(self._pick_size)
        self.size_label = QLabel(self._size_text())
        self.size_label.setFixedWidth(88)
        self.size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.size_slider, 1)
        row.addWidget(self.size_label)
        gl.addLayout(row)
        gl.addWidget(QLabel("每 1 个游戏像素放大成多少物理像素（整数倍最清晰）"))

        self.anim_slider = QSlider(Qt.Horizontal)
        self.anim_slider.setRange(10, 30)
        self.anim_slider.setValue(int(self.win.anim_speed * 10))
        self.anim_slider.valueChanged.connect(self._pick_anim)
        row2 = QHBoxLayout()
        self.anim_label = QLabel(f"{self.win.anim_speed:.1f}x")
        self.anim_label.setFixedWidth(88)
        self.anim_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row2.addWidget(self.anim_slider, 1)
        row2.addWidget(self.anim_label)
        gl.addSpacing(8)
        gl.addLayout(row2)
        gl.addWidget(QLabel("动画速度倍率（1.0x = 与游戏完全一致）"))
        root.addWidget(g)

        g = QGroupBox("开关")
        gl = QVBoxLayout(g)
        self.cb_sound = QCheckBox("音效（神吞笑声 / 激光充能）")
        self.cb_sound.setChecked(self.win.sound_on)
        self.cb_sound.toggled.connect(self._pick_sound)
        gl.addWidget(self.cb_sound)
        self.cb_win = QCheckBox("踩窗口 / 撞窗起跳（把桌面窗口当成实心方块）")
        self.cb_win.setChecked(self.win.use_windows)
        self.cb_win.toggled.connect(self._pick_win)
        gl.addWidget(self.cb_win)
        self.cb_ball = QCheckBox("显示悬浮球")
        self.cb_ball.setChecked(self.win.show_ball)
        self.cb_ball.toggled.connect(self._pick_ball)
        gl.addWidget(self.cb_ball)
        root.addWidget(g)

        g = QGroupBox("音乐")
        gl = QVBoxLayout(g)
        tracks = self.win.music.scan()
        if tracks:
            for i, (label, path) in enumerate(tracks[:8]):
                btn = QPushButton(f"▶  {label}")
                btn.clicked.connect(lambda _=False, k=i: self.win.play_music(k))
                gl.addWidget(btn)
            row_m = QHBoxLayout()
            btn_next = QPushButton("下一首")
            btn_next.clicked.connect(lambda: self.win.music.next())
            btn_stop = QPushButton("⏹ 停止")
            btn_stop.clicked.connect(self.win.stop_music)
            row_m.addWidget(btn_next)
            row_m.addWidget(btn_stop)
            row_m.addStretch(1)
            gl.addLayout(row_m)
        else:
            tip = QLabel("还没有曲目。把 .ogg / .mp3 丢进 assets/music/ 目录，"
                         "重开桌宠就会自动认出来。\n"
                         "文件名含 chaos → 灾祸之仆；含 cosmic/disgust → 寰宇灾劫；\n"
                         "含 collapse/universe/reality → 寰宇破碎。")
            tip.setWordWrap(True)
            gl.addWidget(tip)
        row_v = QHBoxLayout()
        lbl_v = QLabel("音量")
        lbl_v.setFixedWidth(36)
        self.music_vol = QSlider(Qt.Horizontal)
        self.music_vol.setRange(0, 100)
        self.music_vol.setValue(int(self.win.music.volume * 100))
        self.music_vol.valueChanged.connect(
            lambda v: self.win.music.set_volume(v / 100.0))
        row_v.addWidget(lbl_v)
        row_v.addWidget(self.music_vol, 1)
        gl.addLayout(row_v)
        root.addWidget(g)

        self.stat = QLabel("")
        self.stat.setObjectName("stat")
        root.addWidget(self.stat)

        row3 = QHBoxLayout()
        btn_recenter = QPushButton("把神吞召回屏幕中央")
        btn_recenter.clicked.connect(self.win.recenter)
        btn_reset = QPushButton("恢复默认设置")
        btn_reset.clicked.connect(self._reset)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        row3.addWidget(btn_recenter)
        row3.addStretch(1)
        row3.addWidget(btn_reset)
        row3.addWidget(btn_close)
        root.addLayout(row3)
        root.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self._refresh_stat()

    # ---- 读取/写入 -------------------------------------------------------
    def _cur_mult(self):
        return (self.win.scale_chibii if self.win.form == C.FORM_CHIBII
                else self.win.scale_dog)

    def _size_text(self):
        return f"{self._cur_mult():.1f}x"

    def _refresh_stat(self):
        w = self.win
        body = f"v{C.VERSION} · 帧率 {w._fps:.0f} FPS · 逻辑 {C.PET_TICK_HZ:.0f} tick/s"
        if w.form == C.FORM_DOG and w.worm:
            wm = w.worm
            body += (f" · 体节 {len(wm.segments)} · 间距 {wm.spacing():.1f}px"
                     f" · 缩放 {wm.scale:.2f}")
        else:
            body += f" · 贴图帧 {w.chibii.frame}"
        self.stat.setText(body)

    def _pick_form(self, on, key):
        if not on or self._building or key == self.win.form:
            return
        self.win.set_form(key)
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(int(self._cur_mult() * 10))
        self.size_slider.blockSignals(False)
        self.size_label.setText(self._size_text())

    def _pick_mode(self, on, key):
        if not on or self._building or key == self.win.mode:
            return
        self.win.set_mode(key)

    def _pick_size(self, val):
        if self._building:
            return
        self.win.set_scale(self.win.form, val / 10.0)
        self.size_label.setText(self._size_text())

    def _pick_anim(self, val):
        self.anim_label.setText(f"{val / 10.0:.1f}x")
        if self._building:
            return
        self.win.set_anim_speed(val / 10.0)

    def _pick_sound(self, on):
        if not self._building:
            self.win.set_sound(on)

    def _pick_win(self, on):
        if not self._building:
            self.win.set_use_windows(on)

    def _pick_ball(self, on):
        if not self._building:
            self.win.set_show_ball(on)

    def _reset(self):
        self._building = True
        self.win.set_form(C.FORM_DOG)
        self.win.set_scale(C.FORM_DOG, C.DOG_DEFAULT_SCALE)
        self.win.set_scale(C.FORM_CHIBII, 3.0)
        self.win.set_anim_speed(1.0)
        self.win.set_sound(True)
        self.win.set_use_windows(True)
        self.win.set_show_ball(True)
        self.win.set_mode(C.MODE_FOLLOW)
        for rb in self.form_btns.buttons():
            rb.setChecked(C.FORM_LABELS[self.win.form] == rb.text())
        for rb in self.mode_btns.buttons():
            rb.setChecked(C.MODE_LABELS[self.win.mode] == rb.text())
        self.size_slider.setValue(int(self._cur_mult() * 10))
        self.anim_slider.setValue(int(self.win.anim_speed * 10))
        self.cb_sound.setChecked(True)
        self.cb_win.setChecked(True)
        self.cb_ball.setChecked(True)
        self._building = False
        self._refresh_stat()


def _open_launcher(win):
    la = getattr(win, "_launcher_app", None)
    if la is not None:
        la.show_launcher()


def _back_to_launcher(win):
    """收起桌宠，回到启动器界面。"""
    la = getattr(win, "_launcher_app", None)
    if la is not None:
        la.back_to_launcher()
    else:
        win.hide()


def build_control_menu(win, app, on_change=None, menu=None):
    """悬浮球与托盘共用的控制菜单。"""
    m = menu if menu is not None else QMenu()
    m.clear()

    def notify():
        if on_change:
            on_change()

    head = m.addMenu("形态")
    g1 = QActionGroup(head)
    for key, label in C.FORM_LABELS.items():
        a = head.addAction(label)
        a.setCheckable(True)
        a.setChecked(win.form == key)
        g1.addAction(a)

        def _set_form(_=False, k=key):
            win.set_form(k)
            notify()
        a.triggered.connect(_set_form)

    head2 = m.addMenu("模式")
    g2 = QActionGroup(head2)
    for key, label in C.MODE_LABELS.items():
        a = head2.addAction(label)
        a.setCheckable(True)
        a.setChecked(win.mode == key)
        g2.addAction(a)

        def _set_mode(_=False, k=key):
            win.set_mode(k)
            notify()
        a.triggered.connect(_set_mode)

    size = m.addMenu("大小")
    cur_size = win.scale_chibii if win.form == C.FORM_CHIBII else win.scale_dog
    for label, val in C.SIZE_OPTIONS[win.form]:
        a = size.addAction(label)
        a.setCheckable(True)
        a.setChecked(abs(cur_size - val) < 0.01)

        def _set_size(_=False, v=val):
            win.set_scale(win.form, v)
            notify()
        a.triggered.connect(_set_size)

    spd = m.addMenu("动画速度")
    g3 = QActionGroup(spd)
    for label, val in C.ANIM_OPTIONS:
        a = spd.addAction(label)
        a.setCheckable(True)
        a.setChecked(abs(win.anim_speed - val) < 0.01)
        g3.addAction(a)

        def _set_anim(_=False, v=val):
            win.set_anim_speed(v)
            notify()
        a.triggered.connect(_set_anim)

    a = m.addAction("音效")
    a.setCheckable(True)
    a.setChecked(win.sound_on)

    def _toggle_sound():
        win.set_sound(not win.sound_on)
        notify()
    a.triggered.connect(_toggle_sound)

    a = m.addAction("踩窗口 / 撞窗起跳")
    a.setCheckable(True)
    a.setChecked(win.use_windows)

    def _toggle_win():
        win.set_use_windows(not win.use_windows)
        notify()
    a.triggered.connect(_toggle_win)

    a = m.addAction("目标是决心（红心）")
    a.setCheckable(True)
    a.setChecked(win.heart_target)

    def _toggle_heart():
        win.set_heart_target(not win.heart_target)
        notify()
    a.triggered.connect(_toggle_heart)

    a = m.addAction("显示悬浮球")
    a.setCheckable(True)
    a.setChecked(win.show_ball)

    def _toggle_ball():
        win.set_show_ball(not win.show_ball)
        notify()
    a.triggered.connect(_toggle_ball)

    m.addSeparator()
    a = m.addAction("打开启动器")
    a.triggered.connect(lambda: _open_launcher(win))
    music = m.addMenu("🎵 音乐")
    tracks = win.music.scan()
    if tracks:
        for i, (label, path) in enumerate(tracks[:8]):
            act = music.addAction(label)
            act.triggered.connect(lambda _=False, k=i: win.play_music(k))
        music.addSeparator()
        act = music.addAction("⏹ 停止")
        act.triggered.connect(win.stop_music)
    else:
        act = music.addAction("（assets/music/ 里还没有曲目）")
        act.setEnabled(False)
    a = m.addAction("设置…")
    a.triggered.connect(lambda: win.open_settings(app))
    a = m.addAction("召回宠物到屏幕中央")
    a.triggered.connect(lambda: (win.recenter(), notify()))
    a = m.addAction("回到启动器")
    a.triggered.connect(lambda: _back_to_launcher(win))
    a = m.addAction("退出程序")
    a.triggered.connect(app.quit)
    return m


class FloatBall(QWidget):
    """悬浮控制球：拖动移动，单击弹菜单，底部色点指示当前模式。"""

    SIZE = 56

    def __init__(self, win, app):
        super().__init__(None)
        self.win = win
        self.app = app
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setMouseTracking(True)
        self._drag_off = None
        self._hover = False
        self._moved = False
        pos = win.settings.get("ball_pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
        else:
            w = win.world
            self.move(int(w.origin_x + w.W - self.SIZE - 30),
                      int(w.origin_y + w.H * 0.40))
        self.setToolTip("神吞桌宠 · 拖动移动 / 单击打开菜单")

    def _sync_tip(self):
        self.setToolTip(f"神吞桌宠 · {C.FORM_LABELS[self.win.form]} · "
                        f"{C.MODE_LABELS[self.win.mode]}\n拖动移动 / 单击打开菜单")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        s = self.SIZE
        r = QRectF(3.0, 3.0, s - 6.0, s - 6.0)
        p.setPen(QPen(QColor(180, 136, 255, 240 if self._hover else 175), 2.0))
        p.setBrush(QColor(28, 14, 46, 208 if self._hover else 162))
        p.drawEllipse(r)

        pm = self.win.lib.buff
        if not pm.isNull():
            d = 30.0
            p.drawPixmap(QRectF(r.center().x() - d / 2, r.center().y() - d / 2 - 2.5, d, d), pm,
                         QRectF(0, 0, pm.width(), pm.height()))

        col = MODE_COLORS.get(self.win.mode, (200, 200, 200))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(col[0], col[1], col[2], 245))
        p.drawEllipse(QPointF(r.center().x(), s - 13.0), 4.4, 4.4)

        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(QPointF(r.center().x(), 13.5), 3.0, 3.0)
        p.end()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_off = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_off is not None:
            target = e.globalPosition().toPoint() - self._drag_off
            if (target - self.pos()).manhattanLength() > 4:
                self._moved = True
            w = self.win.world
            x = min(max(target.x(), int(w.origin_x)), int(w.origin_x + w.W - self.SIZE))
            y = min(max(target.y(), int(w.origin_y)), int(w.ground_y - self.SIZE))
            self.move(x, y)
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self._drag_off = None
        if self._moved:
            self.win.settings["ball_pos"] = [self.x(), self.y()]
            self.win.save_settings()
        else:
            self.popup()
        e.accept()

    def popup(self):
        self._sync_tip()
        menu = build_control_menu(self.win, self.app, self.update)
        menu.exec(self.mapToGlobal(QPoint(0, self.SIZE + 4)))


class Tray:
    def __init__(self, app, win):
        self.app = app
        self.win = win
        icon = QIcon(win.lib.icon) if not win.lib.icon.isNull() else QIcon(win.lib.buff)
        self.icon = QSystemTrayIcon(icon, app)
        self.menu = build_control_menu(win, app, self.refresh_menu)
        self.menu.aboutToShow.connect(self.refresh_menu)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._on_activate)
        self.icon.show()
        self._sync_tip()

    def refresh_menu(self):
        build_control_menu(self.win, self.app, self.refresh_menu, menu=self.menu)
        self._sync_tip()

    def _sync_tip(self):
        self.icon.setToolTip(f"{C.APP_NAME} · {C.FORM_LABELS[self.win.form]} · "
                             f"{C.MODE_LABELS[self.win.mode]}")

    def _on_activate(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.win.show()
            self.win.raise_()
            self.win.activateWindow()


_MUTEX_HANDLE = None


def acquire_single_instance():
    """命名互斥体：防止重复双击跑出好几只神吞。"""
    global _MUTEX_HANDLE
    try:
        k32 = ctypes.windll.kernel32
        _MUTEX_HANDLE = k32.CreateMutexW(None, False, "Local\\DoGPet_SingleInstance_v1")
        if k32.GetLastError() == 183:      # ERROR_ALREADY_EXISTS
            return False
        return True
    except Exception:
        return True


def run():
    if not acquire_single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(
                0, "神吞已经在桌面上了喵~\n去屏幕或托盘图标那边找它吧。",
                "神吞桌宠", 0x40)
        except Exception:
            pass
        return 0
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    world = World(scale=1.8, use_windows=True)
    win = PetWindow(world)
    win.show()
    tray = Tray(app, win)
    ball = FloatBall(win, app)
    ball.setVisible(win.show_ball)
    win._tray = tray
    win._ball = ball
    return app.exec()
