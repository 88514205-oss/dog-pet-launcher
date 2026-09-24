"""像素风桌宠启动器 · 入口。

流程：启动器窗口（UT 像素风）→ 选模块 → 桌宠宿主跑起来 →
悬浮球 / 托盘的「打开启动器」可以随时回来换模块。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from dogpet import config as C
from dogpet.window import (FloatBall, PetWindow, Tray, acquire_single_instance)
from dogpet.world import World
from launcher_ui import Launcher

ICON = C.APP_NAME


class LauncherApp:
    def __init__(self, app):
        self.app = app
        self.world = World(scale=1.8, use_windows=True)
        self.win = None
        self.tray = None
        self.ball = None
        self.launcher = Launcher(app, None, on_launch=self.launch)
        self.launcher.setWindowIcon(self._icon())

    @staticmethod
    def _icon():
        from PySide6.QtGui import QIcon
        from dogpet import assets
        p = assets.path("dog", "icons", "DoGExtremeGravity.png")
        return QIcon(p) if os.path.isfile(p) else QIcon()

    def _ensure_host(self):
        if self.win is not None:
            return self.win
        win = PetWindow(self.world)
        self.win = win
        win.show()
        self.tray = Tray(self.app, win)
        self.ball = FloatBall(win, self.app)
        self.ball.setVisible(win.show_ball)
        win._tray = self.tray
        win._ball = self.ball
        win._launcher_app = self
        self.tray.refresh_menu()
        return win

    def launch(self, module):
        win = self._ensure_host()
        if getattr(self.launcher, "settings", None):
            win.settings.update(self.launcher.settings)
        win.set_heart_target(getattr(self.launcher, "heart_target", False))
        win.load_module(module)
        win.recenter()
        win.show()
        if self.ball is not None:
            self.ball.setVisible(win.show_ball)

    def back_to_launcher(self):
        """收起桌宠，回到启动器界面。"""
        if self.win is not None:
            self.win.hide()
        self.show_launcher()

    def show_launcher(self):
        self.launcher.refresh()
        self.launcher.show()
        self.launcher.raise_()
        self.launcher.activateWindow()


def main():
    if not acquire_single_instance():
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "桌宠已经在桌面上了喵~\n去屏幕或托盘图标那边找它吧。",
                C.APP_NAME, 0x40)
        except Exception:
            pass
        return 0
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    launcher_app = LauncherApp(app)
    launcher_app.show_launcher()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
