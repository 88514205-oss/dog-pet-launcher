"""素材加载与切帧，全部取自官方 PNG，运行期只读缓存。"""

import os
import sys

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt

from . import config as C


def resource_root():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        cand = os.path.join(base, "assets")
        if os.path.isdir(cand):
            return cand
        return os.path.join(getattr(sys, "_MEIPASS", base), "assets")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "assets")


ASSETS = resource_root()


def path(*parts):
    return os.path.join(ASSETS, *parts)


def load_image(*parts):
    p = path(*parts)
    img = QImage(p)
    if img.isNull():
        raise FileNotFoundError(f"素材缺失: {p}")
    return img.convertToFormat(QImage.Format_ARGB32)


def split_vertical(*parts, frames, frame_size=None):
    """纵向精灵图切帧，返回 QPixmap 列表。"""
    img = load_image(*parts)
    h = img.height() // frames
    w = img.width()
    out = []
    for i in range(frames):
        sub = img.copy(0, i * h, w, h)
        if frame_size is not None:
            sub = sub.scaled(frame_size[0], frame_size[1],
                             Qt.IgnoreAspectRatio, Qt.FastTransformation)
        out.append(QPixmap.fromImage(sub))
    return out


def split_horizontal(*parts, frames):
    """横向精灵图切帧，返回 QPixmap 列表。"""
    img = load_image(*parts)
    w = img.width() // frames
    h = img.height()
    return [QPixmap.fromImage(img.copy(i * w, 0, w, h)) for i in range(frames)]


class Library:
    """一次性加载全部素材并缓存。"""

    def __init__(self):
        self.chibii = split_vertical("chibii", "ChibiiDoggo.png",
                                     frames=C.CHIBII_FRAMES)
        self.chibii_mono = split_vertical("chibii", "ChibiiDoggoMonochrome.png",
                                          frames=C.CHIBII_FRAMES)
        self.fly = split_horizontal("chibii", "ChibiiDoggoFly.png",
                                    frames=C.CHIBII_FLY_FRAMES)
        self.fly_mono = split_horizontal("chibii", "ChibiiDoggoFlyMonochrome.png",
                                         frames=C.CHIBII_FLY_FRAMES)
        self.buff = QPixmap.fromImage(load_image("chibii", "ChibiiDoGBuff.png"))
        self.plushie = QPixmap.fromImage(load_image("chibii", "CosmicPlushie.png"))

        self.dog_p1 = self._dog_parts("phase1", {
            "head": "DevourerofGodsHead.png",
            "head_glow": "DevourerofGodsHeadGlow.png",
            "head_glow2": "DevourerofGodsHeadGlow2.png",
            "body": "DevourerofGodsBody.png",
            "body_glow": "DevourerofGodsBodyGlow.png",
            "tail": "DevourerofGodsTail.png",
            "tail_glow": "DevourerofGodsTailGlow.png",
            "tail_glow2": "DevourerofGodsTailGlow2.png",
        })
        self.dog_p2 = self._dog_parts("phase2", {
            "head": "DevourerofGodsHeadS.png",
            "head_glow": "DevourerofGodsHeadSGlow.png",
            "head_glow2": "DevourerofGodsHeadSGlow2.png",
            "body": "DevourerofGodsBodyS.png",
            "body_glow": "DevourerofGodsBodySGlow.png",
            "body_glow2": "DevourerofGodsBodySGlow2.png",
            "tail": "DevourerofGodsTailS.png",
            "tail_glow": "DevourerofGodsTailSGlow.png",
            "tail_glow2": "DevourerofGodsTailSGlow2.png",
        })
        self.phase2_atlas = self._dog_parts("phase2", {
            "head": "DevourerofGodsHeadS.png",
            "head_glow": "DevourerofGodsHeadSGlow.png",
        })
        self.beam = QPixmap.fromImage(load_image("dog", "projectiles", "DoGBeam.png"))
        self.fire = QPixmap.fromImage(load_image("dog", "projectiles", "DoGFire.png"))
        self.portal = QPixmap.fromImage(load_image("dog", "projectiles", "DoGBeamPortal.png"))
        self.death = QPixmap.fromImage(load_image("dog", "projectiles", "DoGDeath.png"))
        self.icon = QPixmap.fromImage(load_image("dog", "icons", "DoGExtremeGravity.png"))

    @staticmethod
    def _dog_parts(folder, mapping):
        out = {}
        for key, name in mapping.items():
            p = path("dog", folder, name)
            if os.path.exists(p):
                out[key] = QPixmap.fromImage(load_image("dog", folder, name))
        return out


_LIB = None


def library():
    global _LIB
    if _LIB is None:
        _LIB = Library()
    return _LIB
