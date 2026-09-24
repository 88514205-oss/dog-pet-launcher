"""桌宠自检：分项耗时 + 体节几何验证 + 导出预览 PNG。"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from dogpet import config as C
from dogpet.window import PetWindow
from dogpet.world import World

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preview")


def main(form="dog", scale=0.5, mode="follow", frames=240):
    os.makedirs(OUT, exist_ok=True)
    app = QApplication([])
    world = World(use_windows=False)
    win = PetWindow(world)
    win.set_form(form)
    win.set_scale(form, scale)
    win.set_mode(mode)
    win.show()
    for _ in range(40):
        win.step(1.0)

    N = 120
    t = time.perf_counter()
    for _ in range(N):
        win.engine.update(1.0)
        win.particles.update(1.0)
        if form == C.FORM_CHIBII:
            win._step_chibii(1.0)
        else:
            win._step_worm(1.0)
    t_logic = (time.perf_counter() - t) / N * 1000.0

    t = time.perf_counter()
    for _ in range(N):
        win._content_region_global()
    t_region = (time.perf_counter() - t) / N * 1000.0

    W, H = int(world.W), int(world.H)
    img = QImage(W, H, QImage.Format_ARGB32)
    t = time.perf_counter()
    for _ in range(N):
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.translate(-world.origin_x, -world.origin_y)
        win._draw_worm(p) if form == C.FORM_DOG else win._draw_chibii(p)
        p.end()
    t_draw = (time.perf_counter() - t) / N * 1000.0

    print(f"逻辑={t_logic:.2f}ms  脏区={t_region:.2f}ms  绘制={t_draw:.2f}ms  "
          f"合计≈{t_logic+t_region+t_draw:.2f}ms → 上限 {1000/max(t_logic+t_region+t_draw,0.01):.0f} FPS")

    if form == C.FORM_DOG:
        wm = win.worm
        sp = wm.spacing()
        dmin = dmax = None
        worst_ang = 0.0
        for i in range(len(wm.segments)):
            a = wm.c if i == 0 else wm.segments[i - 1].c
            b = wm.segments[i].c
            d = a.distance(b)
            dmin = d if dmin is None else min(dmin, d)
            dmax = d if dmax is None else max(dmax, d)
            expect = (a - b).to_rotation() + math.pi / 2
            diff = abs((wm.rot if i == 0 else wm.segments[i - 1].rot) - wm.segments[i].rot)
            while diff > math.pi:
                diff = abs(diff - 2 * math.pi)
            worst_ang = max(worst_ang, diff)
        print(f"段间距: 期望 {sp:.2f}  实际 [{dmin:.2f} .. {dmax:.2f}]")
        print(f"相邻节最大夹角: {math.degrees(worst_ang):.1f}°")

        body = win.lib.dog_p1.get("body")
        s = wm.scale
        along = body.height() * s
        perp = body.width() * s
        print(f"身段贴图: 沿虫身 {along:.1f}  垂直 {perp:.1f}  间距 {sp:.1f}  "
              f"接缝 {'无缝' if along >= sp - 0.01 else f'缺口 {sp-along:.1f}'}")

        gaps = []
        for i in range(1, len(wm.segments)):
            a = wm.segments[i - 1].c
            b = wm.segments[i].c
            px = int((a.x + b.x) / 2)
            py = int((a.y + b.y) / 2)
            if not (4 <= px < W - 4 and 4 <= py < H - 4):
                continue
            hit = False
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    c = img.pixelColor(px + dx, py + dy)
                    if c.alpha() > 40:
                        hit = True
                        break
                if hit:
                    break
            if not hit:
                gaps.append(i)
        print(f"接缝断点数量: {len(gaps)}  {gaps[:12]}")

    img.save(os.path.join(OUT, f"{form}_{mode}_preview.png"))
    print("预览已导出:", os.path.join(OUT, f"{form}_{mode}_preview.png"))


def edge_check(form="dog", scale=1.5, mode="follow", frames=900):
    app = QApplication([])
    world = World(use_windows=False)
    win = PetWindow(world)
    win.set_form(form)
    win.set_scale(form, scale)
    win.set_mode(mode)
    win.show()
    out_max = 0
    out_frames = 0
    geo_changes = 0
    prev_geo = None
    hit_edge = 0
    for i in range(frames):
        win.step(1.0)
        if win._geo != prev_geo:
            geo_changes += 1
            prev_geo = QRect(win._geo)
        if form == C.FORM_DOG:
            wm = win.worm
            s = wm.scale
            worst = 0.0
            for c, rot, kind in wm.segments_with_head():
                pm = win._dog_pixmap(kind)
                if pm is None:
                    continue
                hw = pm.width() * s * 0.5
                hh = pm.height() * s * 0.5
                d = max(world.origin_x - (c.x - hw), (c.x + hw) - (world.origin_x + world.W),
                        world.origin_y - (c.y - hh), (c.y + hh) - world.ground_y)
                worst = max(worst, d)
            if worst > 0:
                out_frames += 1
                out_max = max(out_max, worst)
            if abs(wm.vel.x) < 0.01 and abs(wm.vel.y) < 0.01:
                pass
        if i == frames - 1:
            print(f"[{form}/{mode}] 窗口几何变更 {geo_changes} 次 / {frames} 帧 "
                  f"(每 {frames/max(geo_changes,1):.0f} 帧一次)")
            if form == C.FORM_DOG:
                print(f"有体节越界的帧数: {out_frames}/{frames}  最大越界 {out_max:.1f} 逻辑px")
    app.quit()


if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else "dog"
    s = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    m = sys.argv[3] if len(sys.argv) > 3 else "follow"
    if "--edge" in sys.argv:
        edge_check(f, s, m)
    else:
        main(f, s, m)
