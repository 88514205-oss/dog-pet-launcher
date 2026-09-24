"""实测窗口绘制/合成耗时：分辨瓶颈在 paint 还是 flush。"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from dogpet import config as C
from dogpet.window import PetWindow
from dogpet.world import World

FRAMES = 300


def main(form, scale, mode):
    app = QApplication([])
    world = World(use_windows=False)
    win = PetWindow(world)
    win.set_form(form)
    win.set_scale(form, scale)
    win.set_mode(mode)
    win.show()

    acc = {"paint": 0.0, "n": 0, "area": 0, "max": 0.0}

    orig = win.paintEvent

    def timed(ev):
        t0 = time.perf_counter()
        orig(ev)
        dt = time.perf_counter() - t0
        acc["paint"] += dt
        acc["n"] += 1
        r = ev.rect()
        acc["area"] += r.width() * r.height()
        acc["max"] = max(acc["max"], dt)

    win.paintEvent = timed

    last = {"t": time.perf_counter()}
    st = {"n": 0, "t0": 0.0, "worst": 0.0, "logic": 0.0, "winarea": 0, "winn": 0}

    def tick():
        now = time.perf_counter()
        dt = now - last["t"]
        last["t"] = now
        if st["n"] == 5:
            st["t0"] = now
            st["worst"] = 0.0
            acc["paint"] = 0.0
            acc["n"] = 0
            acc["area"] = 0
            st["logic"] = 0.0
            st["winarea"] = 0
            st["winn"] = 0
        t0 = time.perf_counter()
        win.step(dt * C.PET_TICK_HZ)
        st["logic"] += time.perf_counter() - t0
        st["winarea"] += win._geo.width() * win._geo.height()
        st["winn"] += 1
        if st["n"] > 5:
            st["worst"] = max(st["worst"], dt)
        st["n"] += 1
        if st["n"] >= FRAMES:
            span = now - st["t0"]
            n = FRAMES - 5
            fps = n / span if span > 0 else 0
            pn = max(acc["n"], 1)
            print(f"FPS={fps:.1f}  最慢单帧={st['worst']*1000:.1f}ms")
            print(f"step 平均={st['logic']/n*1000:.2f}ms")
            print(f"paintEvent 调用={acc['n']}/{n} 次, 平均={acc['paint']/pn*1000:.2f}ms, "
                  f"最大={acc['max']*1000:.1f}ms")
            print(f"paint 脏区平均 {acc['area']/pn/1000:.0f}k px")
            print(f"窗口平均 {st['winarea']/max(st['winn'],1)/1000:.0f}k 逻辑px "
                  f"(全屏 {world.W*world.H/1000:.0f}k)")
            print(f"未解释耗时 ≈ {(span/n - st['logic']/n - acc['paint']/n)*1000:.2f}ms/帧")
            app.quit()
            return
        QTimer.singleShot(16, tick)

    QTimer.singleShot(60, tick)
    app.exec()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dog",
         float(sys.argv[2]) if len(sys.argv) > 2 else 1.5,
         sys.argv[3] if len(sys.argv) > 3 else "follow")
