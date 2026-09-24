"""暴力定位 tmod 里的压缩流：逐个偏移试 raw deflate，成功了就列出内容。"""

import os
import re
import sys
import zlib

MODS = r"C:\Users\akimi\Documents\My Games\Terraria\tModLoader\Mods"


def try_offset(data, off, size=1 << 20):
    try:
        d = zlib.decompressobj(-15)
        out = d.decompress(data[off:off + size])
        if len(out) > 4096:
            return out
    except Exception:
        return None
    return None


def main(name):
    p = os.path.join(MODS, name)
    with open(p, "rb") as f:
        data = f.read(4 << 20)
    print(f"{name}  {os.path.getsize(p)/1024/1024:.1f} MB")
    print("头:", data[:16].hex(), data[:16])
    hits = []
    for off in range(0, 4096):
        out = try_offset(data, off, 1 << 20)
        if out:
            hits.append((off, out))
            if len(hits) >= 3:
                break
    if not hits:
        print("  所有偏移都没解出来")
        return
    for off, out in hits:
        print(f"  偏移 {off} 解出 {len(out)} 字节")
        txt = out[:20000]
        names = set()
        for m in re.finditer(rb"[A-Za-z0-9_ ./\\()'\-]{4,80}\.(?:ogg|wav|mp3|png|xnb)", txt):
            names.add(m.group(0).decode("latin1"))
        for n in sorted(names)[:40]:
            print("     ", n)
        mus = [n for n in names if ".ogg" in n.lower()]
        print(f"  音频文件 {len(mus)} 个")


if __name__ == "__main__":
    for a in (sys.argv[1:] or ["2025.12CalamityModMusic.tmod"]):
        main(a)
