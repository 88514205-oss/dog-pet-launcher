"""抖动量化：逐 tick 记录头部速度/加速度与各体节位移，看是否平滑。"""

import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PySide6.QtWidgets import QApplication

from dogpet.vec import V
from dogpet.window import PetWindow
from dogpet.world import World

N = 900


def main(scale=1.5, mode="follow"):
    app = QApplication([])
    world = World(use_windows=False)
    win = PetWindow(world)
    win.set_form("dog")
    win.set_scale("dog", scale)
    win.set_mode(mode)
    target = V(world.origin_x + world.W * 0.5, world.origin_y + world.H * 0.5)
    world.cursor = lambda: V(target.x, target.y)
    win.show()

    wm = win.worm
    speeds, head, seg_rot, out_of_screen = [], [], [], 0
    seg_disp = []
    worst_out = (0.0, -1, 0.0, 0.0)
    head_tail = []
    prev_seg = [s.c.copy() for s in wm.segments]
    for i in range(N):
        win.physics(1.0)
        speeds.append(wm.vel.length())
        head.append((wm.c.x, wm.c.y))
        head_tail.append(wm.c.distance(wm.segments[-1].c))
        seg_rot.append([s.rot for s in wm.segments])
        disp = 0.0
        for k, s in enumerate(wm.segments):
            disp = max(disp, s.c.distance(prev_seg[k]))
            prev_seg[k] = s.c.copy()
        seg_disp.append(disp)
        best = None
        for idx, (c, rot, kind) in enumerate(wm.segments_with_head()):
            pm = win._dog_pixmap(kind)
            if pm is None:
                continue
            hw = max(pm.width(), pm.height()) * wm.scale * 0.5
            d = max(world.origin_x - (c.x - hw), (c.x + hw) - (world.origin_x + world.W),
                    world.origin_y - (c.y - hw), (c.y + hw) - world.ground_y)
            if best is None or d > best[1]:
                best = (idx, d, c.x, c.y)
        if best and best[1] > 0:
            out_of_screen += 1
            if best[1] > worst_out[0]:
                worst_out = (best[1], best[0], best[2], best[3])

    warm = 220
    dv = [abs(speeds[i] - speeds[i - 1]) for i in range(warm + 1, N)]
    acc = [math.dist(head[i], head[i - 1]) for i in range(warm + 1, N)]
    jolt = [abs(acc[i] - acc[i - 1]) for i in range(1, len(acc))]
    disp = seg_disp[warm:]
    rotjump = []
    for i in range(warm + 1, N):
        worst = 0.0
        for k in range(len(seg_rot[i])):
            d = abs(seg_rot[i][k] - seg_rot[i - 1][k])
            while d > math.pi:
                d = abs(d - 2 * math.pi)
            worst = max(worst, d)
        rotjump.append(worst)

    print(f"[{mode} scale={scale}] 样本 {len(dv)} tick")
    print(f"速度       平均 {statistics.mean(speeds[warm:]):.2f}  px/tick")
    print(f"|Δv|       平均 {statistics.mean(dv):.3f}  最大 {max(dv):.3f}  px/tick")
    print(f"单步位移   平均 {statistics.mean(acc):.3f}  最大 {max(acc):.3f}  px")
    print(f"位移突变   平均 {statistics.mean(jolt):.3f}  最大 {max(jolt):.3f}  px")
    print(f"体节位移   平均 {statistics.mean(disp):.3f}  最大 {max(disp):.3f}  px")
    print(f"体节转角   平均 {math.degrees(statistics.mean(rotjump)):.2f}°  "
          f"最大 {math.degrees(max(rotjump)):.2f}°")
    print(f"体节越界帧 {out_of_screen}/{N}")
    span = []
    for i in range(warm, N):
        pass
    print(f"头尾直线距离 平均 {statistics.mean(head_tail[warm:]):.0f}px "
          f"(虫身总长 {len(wm.segments)*wm.spacing():.0f}px, "
          f"展开率 {statistics.mean(head_tail[warm:])/(len(wm.segments)*wm.spacing())*100:.0f}%)")
    hx = [p[0] for p in head]
    hy = [p[1] for p in head]
    print(f"头部 X 范围 [{min(hx):.0f}, {max(hx):.0f}]  屏 [{world.origin_x:.0f}, "
          f"{world.origin_x + world.W:.0f}]")
    print(f"头部 Y 范围 [{min(hy):.0f}, {max(hy):.0f}]  屏 [{world.origin_y:.0f}, "
          f"{world.ground_y:.0f}]")
    print(f"最远超界 {worst_out[0]:.1f}px 出现在第 {worst_out[1]} 段 "
          f"位置 ({worst_out[2]:.0f},{worst_out[3]:.0f})")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 1.5,
         sys.argv[2] if len(sys.argv) > 2 else "follow")
