"""合成 Undertale 风格的 8-bit 方波 UI 音效。

UT 的界面音就是短促方波：选择是"哔"，确认是上行两声，返回是下行。
用 numpy 直接合成 wav，不依赖任何素材。
"""

import os
import wave

import numpy as np

OUT = r"D:\SCH\DoGPet\assets\ui"
SR = 44100


def square(freq, dur, vol=0.32, decay=9.0, duty=0.5, glide=None):
    """方波 + 指数衰减。glide=(起频, 终频) 可做滑音。"""
    n = int(SR * dur)
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    t = np.arange(n) / SR
    if glide:
        f0, f1 = glide
        f = f0 + (f1 - f0) * (t / max(dur, 1e-6))
        phase = 2 * np.pi * np.cumsum(f) / SR
    else:
        phase = 2 * np.pi * freq * t
    frac = (phase / (2 * np.pi)) % 1.0
    s = np.where(frac < duty, 1.0, -1.0)
    env = np.exp(-decay * t)
    env *= np.minimum(1.0, t * 400.0)          # 掐掉起音爆音
    return (s * env * vol).astype(np.float32)


def silence(dur):
    return np.zeros(int(SR * dur), dtype=np.float32)


def save(path, sig, vol=0.85):
    sig = np.clip(sig * vol, -1.0, 1.0)
    data = (sig * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path, len(data)


SOUNDS = {
    # 移动光标：极短的一声"哔"
    "ui_move": lambda: square(1046.5, 0.045, 0.30, 26.0),
    # 切换卡牌：轻微上行
    "ui_select": lambda: np.concatenate([
        square(880.0, 0.035, 0.30, 22.0),
        square(1174.7, 0.055, 0.28, 18.0),
    ]),
    # 确认启动：UT 那种两声
    "ui_confirm": lambda: np.concatenate([
        square(1318.5, 0.05, 0.32, 16.0),
        silence(0.012),
        square(1760.0, 0.14, 0.30, 8.0),
    ]),
    # 返回 / 收起
    "ui_back": lambda: np.concatenate([
        square(659.3, 0.05, 0.28, 18.0),
        square(440.0, 0.09, 0.26, 12.0),
    ]),
    # 卡牌滑动的"唰"
    "ui_swipe": lambda: square(523.3, 0.10, 0.16, 11.0, glide=(880.0, 392.0)),
    # 卡牌吸附落位
    "ui_snap": lambda: square(1568.0, 0.05, 0.20, 24.0),
    # 报错
    "ui_error": lambda: np.concatenate([
        square(196.0, 0.12, 0.34, 10.0, duty=0.35),
        silence(0.02),
        square(146.8, 0.16, 0.30, 7.0, duty=0.35),
    ]),
}


if __name__ == "__main__":
    total = 0
    for name, fn in SOUNDS.items():
        path = os.path.join(OUT, name + ".wav")
        p, n = save(path, fn())
        total += n
        print(f"  OK  {name:12s} {n/SR*1000:5.0f} ms  -> {path}")
    print(f"共 {len(SOUNDS)} 个音效，{total} 采样")
