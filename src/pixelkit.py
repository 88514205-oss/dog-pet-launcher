"""像素风 UI 工具包（Undertale 味道）。

- 纯黑底 + 硬边白色描边（4px 像素框）
- 中文像素字（Zpix），关抗锯齿，绝不模糊
- 红心光标、打字机文字、方波音效位
"""

import os
import sys

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap)

# ---- 主题（UT 配色） -----------------------------------------------------
BG = QColor(0, 0, 0)
FG = QColor(255, 255, 255)
DIM = QColor(128, 128, 128)
DARK = QColor(40, 40, 40)
YELLOW = QColor(255, 255, 0)
RED = QColor(255, 0, 0)
CYAN = QColor(0, 255, 255)
PURPLE = QColor(168, 120, 255)
GOLD = QColor(200, 168, 78)

FONT_FAMILY = "Zpix"
FONT_FALLBACK = ("Zpix", "Fusion Pixel 12px monospaced zh_hans", "Consolas",
                 "Cascadia Mono", "SimSun")
BASE_PX = 12          # Zpix 的原生设计尺寸；字号自动吸附到它的整数倍才锐利
SCALE = 1             # 这里保持 1，字号本身就用原生倍数控制

_LOADED = False


def ensure_font(assets_root):
    """注册像素字体，失败就退回等宽字体。"""
    global _LOADED
    if _LOADED:
        return FONT_FAMILY
    _LOADED = True
    cands = []
    if assets_root:
        cands.append(os.path.join(assets_root, "fonts", "zpix.ttf"))
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(here, "..", "..", "assets", "fonts", "zpix.ttf"))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cands.insert(0, os.path.join(meipass, "assets", "fonts", "zpix.ttf"))
    for p in cands:
        if p and os.path.isfile(p):
            fid = QFontDatabase.addApplicationFont(os.path.abspath(p))
            if fid >= 0:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    return fams[0]
    return FONT_FAMILY


def font(size=None, bold=False):
    """字号自动吸附到 BASE_PX 的整数倍，避免像素字被非整倍缩放拉糊。"""
    want = float(size or BASE_PX)
    mult = max(1, int(round(want / BASE_PX)))
    px = BASE_PX * mult
    f = QFont()
    for fam in FONT_FALLBACK:
        f.setFamily(fam)
        break
    f.setPixelSize(px)
    f.setBold(bold)
    f.setStyleStrategy(QFont.NoAntialias)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def text_scale(size=None):
    """返回这个字号被吸附成了几倍。"""
    want = float(size or BASE_PX)
    return max(1, int(round(want / BASE_PX)))


def prepare(painter):
    """统一关掉抗锯齿，保证像素硬边。"""
    painter.setRenderHint(QPainter.Antialiasing, False)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
    painter.setRenderHint(QPainter.TextAntialiasing, False)


def text_width(painter, s, size=None):
    painter.setFont(font(size))
    return painter.fontMetrics().horizontalAdvance(s)


def draw_text(painter, x, y, s, color=None, size=None, bold=False):
    painter.setFont(font(size, bold))
    painter.setPen(color or FG)
    painter.drawText(QPointF(x, y), s)
    return text_width(painter, s, size)


# ---- 像素件 --------------------------------------------------------------
def draw_frame(painter, rect, color=None, thickness=4, fill=None):
    """硬边像素框（UT 的对话框就是这种）。"""
    r = QRectF(rect)
    if fill is not None:
        painter.fillRect(r, fill)
    pen = QPen(color or FG, thickness)
    pen.setCapStyle(Qt.SquareCap)
    pen.setJoinStyle(Qt.MiterJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    half = thickness / 2.0
    painter.drawRect(QRectF(r.x() + half, r.y() + half,
                            r.width() - thickness, r.height() - thickness))


def draw_panel(painter, rect, color=None):
    painter.fillRect(QRectF(rect), BG)
    draw_frame(painter, rect, color or FG, 4)


def draw_bar(painter, x, y, w, h, value, back=None, front=None):
    painter.fillRect(QRectF(x, y, w, h), back or DARK)
    v = max(0.0, min(1.0, value))
    painter.fillRect(QRectF(x, y, w * v, h), front or YELLOW)


HEART = (
    " ██ ██ ",
    "███████",
    "███████",
    " █████ ",
    "  ███  ",
    "   █   ",
)


def draw_heart(painter, cx, cy, unit=4, color=None):
    """UT 的红心光标。"""
    painter.setPen(Qt.NoPen)
    painter.setBrush(color or RED)
    n = len(HEART)
    off_x = cx - len(HEART[0]) * unit / 2.0
    off_y = cy - n * unit / 2.0
    for row, line in enumerate(HEART):
        for col, ch in enumerate(line):
            if ch == "█":
                painter.fillRect(QRectF(off_x + col * unit, off_y + row * unit,
                                        unit, unit), color or RED)


def draw_bullet(painter, x, y, unit=4, color=None):
    painter.fillRect(QRectF(x, y, unit * 2, unit * 2), color or FG)


def dotted_line(painter, x1, y1, x2, y2, color=None, step=6, size=2):
    """虚线（像素风分隔线）。"""
    painter.setPen(Qt.NoPen)
    painter.setBrush(color or DARK)
    dx, dy = x2 - x1, y2 - y1
    dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
    n = int(dist // step)
    for i in range(n + 1):
        t = i / max(n, 1)
        painter.fillRect(QRectF(x1 + dx * t, y1 + dy * t, size, size), color or DARK)


def checker_bg(painter, rect, a=None, b=None, cell=8):
    """棋盘格背景（像素风的"透明"表示）。"""
    r = QRectF(rect)
    painter.fillRect(r, a or BG)
    painter.setPen(Qt.NoPen)
    painter.setBrush(b or QColor(16, 16, 16))
    cols = int(r.width() // cell) + 1
    rows = int(r.height() // cell) + 1
    for i in range(cols):
        for j in range(rows):
            if (i + j) % 2:
                painter.fillRect(QRectF(r.x() + i * cell, r.y() + j * cell,
                                        cell, cell), b or QColor(16, 16, 16))


def scale_pixmap(pm, factor):
    """整数倍最近邻放大，保住像素感。"""
    if pm is None or pm.isNull():
        return pm
    from PySide6.QtGui import QTransform
    return pm.transformed(QTransform().scale(factor, factor),
                          Qt.FastTransformation)
