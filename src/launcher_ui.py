"""像素风桌宠启动器 · 卡牌轮播。

- 左右滑动的卡牌，带惯性物理（弹簧吸附 + 阻尼衰减）
- 卡牌上只有角色名字
- 纯黑底、硬边白框、红心光标、UT 风格界面音
- ← → 切换 / Enter 启动 / R 刷新 / Esc 收起，鼠标可直接拖卡牌甩动
"""

import math
import os

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter,
                           QPixmap)

from PySide6.QtWidgets import QWidget

import modkit
import pixelkit as pk

UI_SOUNDS = ("ui_move", "ui_select", "ui_confirm", "ui_back",
             "ui_swipe", "ui_snap", "ui_error")


class CardSound:
    """UT 风格的界面音（合成出来的 wav，QSoundEffect 就能放）。"""

    def __init__(self, parent=None, assets_root=None):
        self.pool = {}
        self.ok = False
        base = os.path.join(assets_root or "", "ui")
        cands = [base]
        here = os.path.dirname(os.path.abspath(__file__))
        cands.append(os.path.join(here, "..", "assets", "ui"))
        try:
            from PySide6.QtMultimedia import QSoundEffect
        except Exception:
            return
        for name in UI_SOUNDS:
            path = None
            for d in cands:
                p = os.path.join(d, name + ".wav")
                if os.path.isfile(p):
                    path = p
                    break
            if path is None:
                continue
            eff = QSoundEffect(parent)
            eff.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
            eff.setVolume(0.55)
            self.pool[name] = eff
        self.ok = bool(self.pool)

    def play(self, name, vol=None):
        eff = self.pool.get(name)
        if eff is None:
            return
        if vol is not None:
            eff.setVolume(vol)
        eff.stop()
        eff.play()


class Card:
    W = 236
    H = 320
    GAP = 1.28          # 卡牌间距（相对卡宽，越大离得越远）


def dominant_color(pm):
    """取图标主色调：量化后投票，忽略过暗和过透的像素。"""
    if pm is None or pm.isNull():
        return QColor(200, 168, 78)
    img = pm.toImage().scaled(32, 32, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    buckets = {}
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 120:
                continue
            r, g, b = c.red(), c.green(), c.blue()
            if r + g + b < 90:
                continue
            key = (r // 32, g // 32, b // 32)
            e = buckets.setdefault(key, [0, 0, 0, 0])
            e[0] += r
            e[1] += g
            e[2] += b
            e[3] += 1
    if not buckets:
        return QColor(200, 168, 78)
    best = max(buckets.values(), key=lambda e: e[3])
    n = max(best[3], 1)
    r, g, b = best[0] // n, best[1] // n, best[2] // n
    # 提亮一点，当渐变底色更好看
    mx = max(r, g, b, 1)
    boost = min(1.55, 215.0 / mx)
    return QColor(min(255, int(r * boost)), min(255, int(g * boost)),
                  min(255, int(b * boost)))


class Launcher(QWidget):
    PAD = 34

    def __init__(self, app, host_factory=None, on_launch=None, assets_root=None,
                 settings=None):
        super().__init__(None)
        self.app = app
        self.on_launch = on_launch
        self.settings = settings if settings is not None else {}
        self.heart_target = bool(self.settings.get("heart_target", False))
        self.modules = []
        self.pos = 0.0          # 浮点卡牌位置
        self.vel = 0.0          # 惯性速度
        self.target = 0.0       # 吸附目标
        self.dragging = False
        self._drag_x = 0.0
        self._drag_pos0 = 0.0
        self._last_x = 0.0
        self._last_t = 0.0
        self._fling = 0.0
        self._snapped = 0
        self.hint_blink = 0.0
        self.float_t = 0.0
        self.theme = QColor(200, 168, 78)
        self.snd = CardSound(self, assets_root)
        pk.ensure_font(assets_root)

        self.setWindowTitle("桌宠启动器")
        self.setStyleSheet("background:#000;")
        self.setMinimumSize(820, 600)
        self.resize(1040, 700)
        self.setMouseTracking(True)
        self.refresh()

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._step)
        self.timer.start()

    # ---- 模块 ------------------------------------------------------------
    def refresh(self):
        self.modules = modkit.scan()
        for m in self.modules:
            m.validate()
        self.pos = min(self.pos, max(0, len(self.modules) - 1))
        self.target = round(self.pos)
        self._snapped = int(self.target)
        self._sync_theme()
        self.update()

    def _cur_index(self):
        if not self.modules:
            return -1
        i = int(round(self.pos))
        return max(0, min(i, len(self.modules) - 1))

    def _selected(self):
        i = self._cur_index()
        return self.modules[i] if i >= 0 else None

    # ---- 物理 ------------------------------------------------------------
    def _step(self):
        self.hint_blink = (self.hint_blink + 0.045) % 1.0
        self.float_t += 0.028
        if not self.dragging and self.modules:
            # 软弹簧 + 弱阻尼：滑过去会明显越过一点点，再被拉回来
            k = 0.026
            damp = 0.915
            self.vel += (self.target - self.pos) * k
            self.vel *= damp
            if abs(self.vel) < 0.0006:
                self.vel = 0.0
            self.pos += self.vel
            if abs(self.vel) < 0.0006 and abs(self.target - self.pos) < 0.02:
                self.pos = self.target
            idx = self._cur_index()
            if idx != self._snapped:
                self._snapped = idx
                self._sync_theme()
                self.snd.play("ui_select", 0.42)
        self.update()

    def _nudge(self, d):
        """键盘切换：给一个初速度，让卡牌滑过去。"""
        if not self.modules:
            return
        n = len(self.modules)
        self.target = max(0.0, min(float(n - 1), self.target + d))
        self.vel = d * 0.055
        self.snd.play("ui_move", 0.5)

    def _sync_theme(self):
        m = self._selected()
        self.theme = dominant_color(QPixmap(m.icon_path())) if (m and m.icon_path()) \
            else QColor(200, 168, 78)

    # ---- 交互 ------------------------------------------------------------
    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Right, Qt.Key_D):
            self._nudge(1)
        elif k in (Qt.Key_Left, Qt.Key_A):
            self._nudge(-1)
        elif k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._launch()
        elif k == Qt.Key_R:
            self.refresh()
            self.snd.play("ui_snap", 0.5)
        elif k == Qt.Key_T:
            self._toggle_target()
        elif k == Qt.Key_Escape:
            self.snd.play("ui_back", 0.45)
            self.hide()
        elif Qt.Key_1 <= k <= Qt.Key_9:
            i = k - Qt.Key_1
            if i < len(self.modules):
                self.target = float(i)
                self.vel += (self.target - self.pos) * 0.25
                self.snd.play("ui_move", 0.5)

    def _card_at(self, pos):
        """点到了哪张卡牌（-1 表示没点到）。"""
        cx = self.width() / 2.0
        cy = self.height() / 2.0 - 52 + math.sin(self.float_t) * 9.0
        for i in range(len(self.modules)):
            d = i - self.pos
            if abs(d) > 3.2:
                continue
            scale = max(0.36, 1.0 - abs(d) * 0.30)
            cw, ch = Card.W * scale, Card.H * scale
            bx = cx + d * (Card.W * Card.GAP) - cw / 2
            by = cy - ch / 2 + abs(d) * 10
            if QRectF(bx, by, cw, ch).contains(pos):
                return i
        return -1

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._in_target_row(e.position()):
            self._toggle_target()
            e.accept()
            return
        # 点卡牌 = 选中它（滑到中间）；双击才启动
        idx = self._card_at(e.position())
        if idx >= 0:
            if idx != self._cur_index():
                self.target = float(idx)
                self.vel = 0.0
                self.snd.play("ui_move", 0.5)
            e.accept()
            return
        self.dragging = True
        self._drag_x = e.position().x()
        self._drag_pos0 = self.pos
        self._last_x = self._drag_x
        self._fling = 0.0

    def mouseMoveEvent(self, e):
        if not self.dragging:
            return
        x = e.position().x()
        dx = x - self._drag_x
        self.pos = self._drag_pos0 - dx / (Card.W * Card.GAP)
        n = max(len(self.modules) - 1, 0)
        self.pos = max(-0.7, min(float(n) + 0.7, self.pos))
        self._fling = (x - self._last_x) / (Card.W * Card.GAP)
        self._last_x = x
        idx = self._cur_index()
        if idx != self._snapped:
            self._snapped = idx
            self._sync_theme()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.dragging:
            return
        self.dragging = False
        n = max(len(self.modules) - 1, 0)
        # 甩动惯性：把拖拽末速交给物理系统，再按落点估算要停在哪张
        self.vel = -self._fling * 1.1
        guess = self.pos + self.vel * 6.0
        self.target = float(max(0, min(n, int(round(guess)))))
        if abs(self.vel) > 0.02:
            self.snd.play("ui_swipe", 0.4)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._launch()

    # ---- 目标切换 --------------------------------------------------------
    def _toggle_target(self):
        """切换追踪目标：鼠标 ⇄ 决心（红心）。"""
        self.heart_target = not self.heart_target
        self.settings["heart_target"] = self.heart_target
        try:
            from dogpet.window import save_settings
            save_settings(self.settings)
        except Exception:
            pass
        self.snd.play("ui_move", 0.5)
        self.update()

    def _target_row_rect(self):
        return QRectF(self.width() * 0.5 - 190, self.height() - 96, 380, 40)

    def _in_target_row(self, pos):
        return self._target_row_rect().contains(pos)

    def _launch(self):
        m = self._selected()
        if m is None:
            self.snd.play("ui_error")
            return
        problems = m.validate()
        if problems:
            self.snd.play("ui_error")
            return
        if self.on_launch:
            self.on_launch(m)
        self.snd.play("ui_confirm", 0.6)
        QTimer.singleShot(160, self.hide)

    # ---- 绘制 ------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        pk.prepare(p)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, pk.BG)
        self._draw_dots(p, w, h)
        self._draw_gradient(p, w, h)

        if not self.modules:
            msg = "pets/ 目录里没有模块"
            mw = pk.text_width(p, msg, 12)
            pk.draw_text(p, (w - mw) / 2, h / 2, msg, pk.DIM, 12)
            p.end()
            return

        c = self.theme
        # 顶部：细标题 + 主色装饰线
        title = "P E T   L A U N C H E R"
        tw = pk.text_width(p, title, 24)
        pk.draw_text(p, (w - tw) / 2, 40, title, QColor(168, 168, 178), 24)
        pk.dotted_line(p, w / 2 - 120, 56, w / 2 + 120, 56,
                       QColor(c.red(), c.green(), c.blue(), 170), 8, 3)

        # 整组卡牌缓慢上下浮动，做出呼吸感
        float_y = math.sin(self.float_t) * 9.0
        cy = h / 2 - 52 + float_y
        n = len(self.modules)
        order = sorted(range(n), key=lambda i: -abs(i - self.pos))
        for i in order:
            d = i - self.pos
            if abs(d) > 3.2:
                continue
            self._draw_card(p, i, d, w / 2, cy)

        idx = self._cur_index()
        name = self.modules[idx].name if 0 <= idx < n else ""
        nw = pk.text_width(p, name, 36)
        pk.draw_text(p, (w - nw) / 2, cy + Card.H / 2 + 52, name, pk.FG, 36, True)

        pk.dotted_line(p, w / 2 - 52, cy + Card.H / 2 + 66, w / 2 + 52,
                       cy + Card.H / 2 + 66,
                       QColor(c.red(), c.green(), c.blue(), 200), 8, 3)

        # 目标选项（点它或者按 T 切换）
        rr = self._target_row_rect()
        on = self.heart_target
        pk.draw_frame(p, rr, QColor(150, 150, 160) if not on else QColor(255, 60, 60), 3)
        lab = f"目标： {'决心' if on else '鼠标'}"
        lw = pk.text_width(p, lab, 24)
        pk.draw_text(p, rr.center().x() - lw / 2, rr.center().y() + 9, lab,
                     QColor(255, 90, 90) if on else pk.FG, 24, on)

        tips = "← →  切换     Enter  启动     T  目标     R  刷新     Esc  收起"
        tw2 = pk.text_width(p, tips, 24)
        pk.draw_text(p, (w - tw2) / 2, h - 30, tips, QColor(110, 110, 120), 24)
        p.end()

    def _draw_dots(self, p, w, h):
        """背景细点阵：比星星安静，也更干净。"""
        p.setPen(Qt.NoPen)
        for y in range(12, h, 26):
            for x in range(14, w, 26):
                p.fillRect(x, y, 1, 1, QColor(26, 26, 30))

    def _draw_gradient(self, p, w, h):
        """底部渐变，颜色跟着当前卡牌的主色调走。"""
        c = self.theme
        grad = QLinearGradient(0, h * 0.30, 0, h)
        grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 0))
        grad.setColorAt(0.62, QColor(c.red(), c.green(), c.blue(), 18))
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 62))
        p.fillRect(QRectF(0, h * 0.30, w, h * 0.70), QBrush(grad))

    def _draw_stars(self, p, w, h):
        """背景点阵，像素风的星空。"""
        p.setPen(Qt.NoPen)
        seed = 20240919
        for i in range(70):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            sx = (seed >> 7) % max(w, 1)
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            sy = (seed >> 7) % max(h, 1)
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            v = 30 + (seed >> 9) % 46
            p.fillRect(sx, sy, 2, 2, QColor(v, v, v))

    def _draw_card(self, p, i, d, cx, cy):
        m = self.modules[i]
        ad = abs(d)
        scale = max(0.36, 1.0 - ad * 0.30)
        alpha = max(0.10, 1.0 - ad * 0.42)
        sel = ad < 0.5
        cw = Card.W * scale
        ch = Card.H * scale
        x = cx + d * (Card.W * Card.GAP) - cw / 2
        y = cy - ch / 2 + ad * 10

        r = QRectF(x, y, cw, ch)
        p.save()
        p.setOpacity(alpha)

        if sel:
            c = self.theme
            # 主色调柔光（三层递减），比粗白框精致
            for k, a in ((9, 26), (5, 40), (2, 60)):
                p.fillRect(r.adjusted(-k, -k, k, k),
                           QColor(c.red(), c.green(), c.blue(), a))
            grad = QLinearGradient(r.x(), r.y(), r.x(), r.bottom())
            grad.setColorAt(0.0, QColor(30, 30, 36))
            grad.setColorAt(0.5, QColor(12, 12, 16))
            grad.setColorAt(1.0, QColor(7, 7, 9))
            p.fillRect(r, QBrush(grad))
            pk.draw_frame(p, r, QColor(238, 238, 244), 2)
            # 左上角一小截主色描边，做"高光角"
            p.fillRect(QRectF(r.x(), r.y(), cw * 0.34, 2),
                       QColor(c.red(), c.green(), c.blue(), 220))
            p.fillRect(QRectF(r.x(), r.y(), 2, ch * 0.16),
                       QColor(c.red(), c.green(), c.blue(), 220))
        else:
            p.fillRect(r, QColor(6, 6, 8))
            pk.draw_frame(p, r, QColor(48, 48, 56), 2)

        ic = m.icon_path()
        if ic:
            pm = QPixmap(ic)
            if not pm.isNull():
                side = cw * 0.50
                pm = pm.scaled(int(side), int(side), Qt.KeepAspectRatio,
                               Qt.FastTransformation)
                if not sel:
                    p.setOpacity(alpha * 0.55)
                p.drawPixmap(int(x + (cw - pm.width()) / 2),
                             int(y + ch * 0.34 - pm.height() / 2), pm)
                p.setOpacity(alpha)

        if sel:
            # 卡内底部一条主色细线
            p.fillRect(QRectF(r.x() + cw * 0.30, r.bottom() - 10, cw * 0.40, 2),
                       QColor(self.theme.red(), self.theme.green(),
                              self.theme.blue(), 170))
        p.restore()
