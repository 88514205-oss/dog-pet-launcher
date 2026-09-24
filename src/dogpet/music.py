"""BGM 播放器：扫描 assets/music 下的曲目，用 QMediaPlayer 播放。

曲目槽位按文件名关键词自动对号入座，所以曲名写成什么样都能认出来。
"""

import os

from PySide6.QtCore import QObject, QUrl

from . import assets

# 槽位：(标签, 关键词)。关键词命中文件名即归入该槽位。顺序很重要（先匹配先归属）。
SLOT_HINTS = (
    ("灾祸之仆", ("servant", "chaos", "仆从", "天灾之仆", "灾祸之仆")),
    ("寰宇灾劫", ("eulogy", "scourge of the universe", "寰宇灾劫", "灾劫")),
    ("寰宇碎灭", ("collapse", "universal", "碎灭", "破碎", "寰宇碎")),
)

EXTS = (".ogg", ".mp3", ".wav", ".flac", ".m4a")


class MusicPlayer(QObject):
    """懒加载的 BGM 播放器；没有 QtMultimedia 时静默降级。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.output = None
        self.volume = 0.55
        self.tracks = []          # [(label, path)]
        self.index = -1
        self._failed = False
        self.scan()

    # ---- 曲库 -----------------------------------------------------------
    def music_dir(self):
        return assets.path("music")

    def cache_dirs(self):
        """回退来源：tModLoader 播放过的音乐会被缓存下来，直接拿来用。"""
        home = os.path.expanduser("~")
        return (
            os.path.join(home, "Documents", "My Games", "Terraria",
                         "tModLoader", "TrackedMusic"),
        )

    def _classify(self, name):
        low = name.lower()
        for slot_label, keys in SLOT_HINTS:
            if any(k in low for k in keys):
                return slot_label
        return os.path.splitext(name)[0]

    def scan(self):
        found = []
        seen = set()
        d = self.music_dir()
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if name.lower().endswith(EXTS):
                    found.append((self._classify(name), os.path.join(d, name)))
                    seen.add(name.lower())
        if not found:
            for root in self.cache_dirs():
                if not os.path.isdir(root):
                    continue
                for dirpath, _dirs, files in os.walk(root):
                    for name in sorted(files):
                        if not name.lower().endswith(EXTS):
                            continue
                        if name.lower() in seen:
                            continue
                        seen.add(name.lower())
                        found.append((self._classify(name),
                                      os.path.join(dirpath, name)))
                    if len(found) >= 24:
                        break
        order = {label: i for i, (label, _keys) in enumerate(SLOT_HINTS)}
        found.sort(key=lambda x: (order.get(x[0], 99), x[0]))
        self.tracks = found
        return found

    def has_tracks(self):
        return len(self.tracks) > 0

    # ---- 播放控制 --------------------------------------------------------
    def _ensure(self):
        if self.player is not None:
            return True
        if self._failed:
            return False
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception:
            self._failed = True
            return False
        self.output = QAudioOutput()
        self.output.setVolume(self.volume)
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._on_status)
        return True

    def _on_status(self, status):
        try:
            from PySide6.QtMultimedia import QMediaPlayer
        except Exception:
            return
        if status == QMediaPlayer.EndOfMedia and self.player is not None:
            self.play_index(self.index + 1)

    def play_index(self, idx):
        if not self.tracks:
            self.scan()
        if not self.tracks:
            return None
        if not self._ensure():
            return None
        idx %= len(self.tracks)
        label, path = self.tracks[idx]
        self.index = idx
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        return label

    def play_slot(self, slot):
        """按槽位序号播放（0/1/2 对应三首主题曲）。"""
        if slot < len(self.tracks):
            return self.play_index(slot)
        return None

    def next(self):
        return self.play_index(self.index + 1)

    def stop(self):
        if self.player is not None:
            self.player.stop()
        self.index = -1

    def toggle(self):
        if self.player is not None and self.player.isPlaying():
            self.stop()
            return False
        return self.play_index(0 if self.index < 0 else self.index) is not None

    def set_volume(self, v):
        self.volume = max(0.0, min(1.0, float(v)))
        if self.output is not None:
            self.output.setVolume(self.volume)

    def current_label(self):
        if 0 <= self.index < len(self.tracks):
            return self.tracks[self.index][0]
        return None

    def is_playing(self):
        return self.player is not None and self.player.isPlaying()
