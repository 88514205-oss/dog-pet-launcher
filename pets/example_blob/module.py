"""示例模块 · 一个跟着鼠标跑的像素方块。

这是**最小可用**的桌宠模块：复制整个文件夹、改个名字，就是一个新桌宠了。
注释里写清了每个方法什么时候会被调用。
"""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QRegion

from dogpet.vec import V


def create(host):
    """模块入口：返回你的宠物实例。host 是宿主，能拿屏幕、粒子、音效等。"""
    return Blob(host)


class Blob:
    SIZE = 22

    def __init__(self, host):
        self.host = host
        w = host.world
        self.pos = V(w.origin_x + w.W * 0.5, w.origin_y + w.H * 0.5)
        self.vel = V()

    # ---- 必须实现的两个 ----
    def update(self, ticks):
        """每 tick 调一次（60 tick/s）。ticks 一般是 1.0。"""
        t = self.host.engine.target.pos      # 当前追踪点（鼠标 / 巡游点 / 星体）
        k = 0.09 * ticks
        self.vel.x += ((t.x - self.pos.x) - self.vel.x) * k
        self.vel.y += ((t.y - self.pos.y) - self.vel.y) * k
        self.pos.x += self.vel.x * ticks
        self.pos.y += self.vel.y * ticks

    def draw(self, p, host):
        """每帧画一次。坐标原点已经是屏幕左上角。"""
        x, y, s = int(self.pos.x), int(self.pos.y), self.SIZE
        p.fillRect(QRect(x, y, s, s), QColor(255, 255, 255))
        p.fillRect(QRect(x + 5, y + 6, 5, 5), QColor(0, 0, 0))
        p.fillRect(QRect(x + s - 10, y + 6, 5, 5), QColor(0, 0, 0))

    # ---- 可选：不做也能跑 ----
    def bounds(self):
        """告诉宿主要重绘哪块，能省很多性能。"""
        pad = 90
        return QRegion(QRect(int(self.pos.x - pad), int(self.pos.y - pad),
                             self.SIZE + pad * 2, self.SIZE + pad * 2))

    def render_box(self):
        """鼠标命中范围，用来支持拖动。"""
        return (self.pos.x - 10, self.pos.y - 10, self.SIZE + 20, self.SIZE + 20)

    def pet_position(self):
        return V(self.pos.x, self.pos.y)

    def place(self, gx, gy):
        self.pos = V(gx, gy)
        self.vel = V()

    def recenter(self):
        w = self.host.world
        self.pos = V(w.origin_x + w.W * 0.5, w.origin_y + w.H * 0.5)
        self.vel = V()
