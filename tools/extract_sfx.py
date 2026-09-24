"""从 Terraria 的 XNB 音效里直接抽出 WAV。

Terraria 的 Content/Sounds/*.xnb 是标准 XNB 包裹的音频，
音频数据本身是 RIFF/WAVE，按标记切出来即可。
"""

import os
import struct
import sys

SRC = r"D:\SteamLibrary\steamapps\common\Terraria\Content\Sounds"
OUT = r"D:\SCH\DoGPet\assets\sfx"

# 需要哪几个音效：本地名 -> 目标名
WANTED = {
    "Female_Hit_0": "player_hurt0",
    "Female_Hit_1": "player_hurt1",
    "Female_Hit_2": "player_hurt2",
    "Male_Hit_0": "player_hurt_m0",
    "NPC_Hit_1": "npc_hit1",
    "NPC_Killed_1": "npc_killed1",
    "Item_1": "item_swing",
    "Bone_Laser": "bone_laser",
    "Eye_Laser": "eye_laser",
    "Eye_Laser_Small": "eye_laser_small",
    "Roar_0": "roar0",
    "Roar_1": "roar1",
    "Explosion_0": "explosion0",
    "Explosion_1": "explosion1",
    "Thunder_0": "thunder0",
}


def find_wave(data):
    """在 XNB 里定位 RIFF/WAVE 数据块，返回 (offset, length)。"""
    i = data.find(b"RIFF")
    while i != -1:
        if i + 12 <= len(data) and data[i + 8:i + 12] == b"WAVE":
            size = struct.unpack_from("<I", data, i + 4)[0] + 8
            if 44 < size <= len(data) - i:
                return i, size
            return i, len(data) - i
        i = data.find(b"RIFF", i + 1)
    # 有些是 ADPCM，用 fmt 标记定位
    j = data.find(b"fmt ")
    if j != -1:
        start = max(0, j - 8)
        k = data.find(b"data", j)
        if k != -1:
            dsize = struct.unpack_from("<I", data, k + 4)[0]
            end = min(len(data), k + 8 + dsize)
            riff = b"RIFF" + struct.pack("<I", end - start - 8) + b"WAVE"
            return ("synthetic", start, end, riff)
    return None


def extract(name):
    src = os.path.join(SRC, name + ".xnb")
    if not os.path.exists(src):
        return None
    with open(src, "rb") as f:
        data = f.read()
    if data[:3] != b"XNB":
        return None
    hit = find_wave(data)
    if hit is None:
        return None
    if isinstance(hit[0], str):
        _, start, end, riff = hit
        body = riff + data[start + 12:end]
    else:
        off, size = hit
        body = data[off:off + size]
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, WANTED[name] + ".wav")
    with open(dst, "wb") as f:
        f.write(body)
    return dst, len(body)


if __name__ == "__main__":
    names = sys.argv[1:] or list(WANTED.keys())
    ok = 0
    for n in names:
        r = extract(n)
        if r:
            print(f"  OK  {n:22s} -> {os.path.basename(r[0])}  {r[1]/1024:.0f} KB")
            ok += 1
        else:
            print(f"  --  {n:22s} 提取失败/不存在")
    print(f"成功 {ok}/{len(names)}")
