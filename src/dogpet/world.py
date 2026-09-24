"""桌面世界：屏幕几何、鼠标目标、以 16px 为一格的实心判定。

桌宠把「桌面」当作 Terraria 世界：工作区底边是地面，屏幕左右是墙，
可选把其它窗口的矩形当作实心块，于是宠物会踩在窗口上、撞到窗口边会起跳。
"""

import ctypes
from ctypes import wintypes

from PySide6.QtGui import QCursor, QGuiApplication

from .vec import V

TILE = 16.0


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


def _list_windows():
    """枚举可见顶层窗口矩形，返回自适应缩放前的物理像素矩形列表。"""
    user32 = ctypes.windll.user32
    out = []
    own_pid = ctypes.windll.kernel32.GetCurrentProcessId()

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True
        style = user32.GetWindowLongW(hwnd, -20)
        if style & 0x00000080:      # WS_EX_TOOLWINDOW
            return True
        ex = user32.GetWindowLongW(hwnd, -16)
        if ex == 0:
            return True
        r = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return True
        w = r.right - r.left
        h = r.bottom - r.top
        if w < 120 or h < 60:
            return True
        out.append((r.left, r.top, r.right, r.bottom))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


class World:
    def __init__(self, scale=1.8, use_windows=True):
        self.scale = scale
        self.use_windows = use_windows
        self._win_rects = []
        self._win_tick = 0
        self.refresh()

    def refresh(self):
        scr = QGuiApplication.primaryScreen()
        self.geo = scr.geometry()
        self.work = scr.availableGeometry()
        self.dpr = scr.devicePixelRatio()
        self.W = float(self.work.width())
        self.H = float(self.work.height())
        self.origin_x = float(self.work.x())
        self.origin_y = float(self.work.y())
        self.ground_y = float(self.work.y() + self.work.height())

    def pixel_scale(self, physical_multiple):
        """把「每个游戏像素占多少物理像素」换算成逻辑坐标缩放，保证像素完美。"""
        return float(physical_multiple) / max(self.dpr, 0.01)

    def tick(self):
        self._win_tick -= 1
        if self.use_windows and self._win_tick <= 0:
            self._win_tick = 24
            self._reload_windows()

    def _reload_windows(self):
        try:
            raw = _list_windows()
        except Exception:
            self._win_rects = []
            return
        d = self.dpr
        rects = []
        for (l, t, r, b) in raw:
            x0, y0 = l / d, t / d
            x1, y1 = r / d, b / d
            if x1 - x0 > self.W * 0.98 and y1 - y0 > self.H * 0.98:
                continue
            rects.append((x0, y0, x1, y1))
        self._win_rects = rects

    def cursor(self):
        p = QCursor.pos()
        return V(float(p.x()), float(p.y()))

    def clamp_to_work(self, v):
        v.x = min(max(v.x, self.origin_x + 8), self.origin_x + self.W - 8)
        v.y = min(max(v.y, self.origin_y + 8), self.ground_y - 8)
        return v

    def in_work(self, x, y):
        return (self.origin_x <= x <= self.origin_x + self.W and
                self.origin_y <= y <= self.ground_y)

    def solid_rect_at(self, x, y):
        """返回该点命中的实心矩形（窗口），没有则 None。"""
        for (x0, y0, x1, y1) in self._win_rects:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return (x0, y0, x1, y1)
        return None

    def solid_at(self, x, y):
        if y >= self.ground_y:
            return True
        if x <= self.origin_x or x >= self.origin_x + self.W:
            return True
        if self.use_windows and self.solid_rect_at(x, y) is not None:
            return True
        return False

    def solid_at_scaled(self, x, y):
        """以宠物自身缩放为准的实心判定（坐标已是屏幕逻辑像素）。"""
        return self.solid_at(x, y)
