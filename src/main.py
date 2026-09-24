"""神吞桌面宠物 · 入口

用法：
    python main.py              正常启动桌宠
    python main.py --selftest N 无交互自检 N 帧并输出帧率
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from dogpet import config as C
from dogpet.window import FloatBall, PetWindow, Tray, acquire_single_instance
from dogpet.world import World


def selftest(frames, form=None, mode=None, scale=None):
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    world = World(scale=1.8, use_windows=False)
    win = PetWindow(world)
    if form:
        win.set_form(form)
    if mode:
        win.set_mode(mode)
    if scale is not None:
        win.set_scale(win.form, scale)
    win.show()
    print(f"屏 {world.W:.0f}x{world.H:.0f} 原点({world.origin_x:.0f},{world.origin_y:.0f}) "
          f"地面Y={world.ground_y:.0f} dpr={world.dpr} 形态={win.form} 模式={win.mode}")

    state = {"n": 0, "t0": 0.0, "worst": 0.0}
    last = {"t": time.perf_counter()}

    def tick():
        now = time.perf_counter()
        dt = now - last["t"]
        last["t"] = now
        if state["n"] == 3:
            state["t0"] = now
            state["worst"] = 0.0
        win.step(dt * C.PET_TICK_HZ)
        if state["n"] > 3:
            state["worst"] = max(state["worst"], dt)
        state["n"] += 1
        if state["n"] >= frames:
            span = now - state["t0"]
            fps = (frames - 3) / span if span > 0 else 0.0
            print(f"渲染 {frames} 帧耗时 {span*1000:.0f} ms → {fps:.1f} FPS "
                  f"(最慢单帧 {state['worst']*1000:.1f} ms)")
            if win.form == C.FORM_CHIBII:
                p = win.chibii
                print(f"Q版位置 ({p.pos.x:.1f},{p.pos.y:.1f}) 帧={p.frame} "
                      f"飞行={p.fly_mode} 速度=({p.vel.x:.2f},{p.vel.y:.2f}) 朝={p.sprite_direction} "
                      f"缩放={p.scale:.3f}")
            else:
                w = win.worm
                print(f"本体位置 ({w.c.x:.1f},{w.c.y:.1f}) 段数={len(w.segments)} "
                      f"状态={w.state} 速度={w.vel.length():.2f} 缩放={w.scale:.3f}")
            app.quit()
            return
        QTimer.singleShot(16, tick)

    last["t"] = time.perf_counter()
    QTimer.singleShot(60, tick)
    return app.exec()


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        i = args.index("--selftest")
        frames = int(args[i + 1]) if len(args) > i + 1 else 180
        form = args[args.index("--form") + 1] if "--form" in args else None
        mode = args[args.index("--mode") + 1] if "--mode" in args else None
        scale = float(args[args.index("--scale") + 1]) if "--scale" in args else None
        return selftest(frames, form, mode, scale)

    if not acquire_single_instance():
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "神吞已经在桌面上了喵~\n去屏幕或托盘图标那边找它吧。",
                "神吞桌宠", 0x40)
        except Exception:
            pass
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
