"""从灾厄维基的静态资源站下载神明吞噬者音效。"""

import os
import urllib.parse
import urllib.request

OUT = r"D:\SCH\DoGPet\assets\sfx"
BASE = "https://huiji-public.huijistatic.com/calamity/uploads/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://calamity.huijiwiki.com/"}

WANTED = {
    "dog_spawn": "3/38/神吞生成.ogg",
    "dog_teleport": "4/45/神吞传送.ogg",
    "dog_laserwall_spawn": "e/e0/神吞激光墙生成.ogg",
    "dog_laserwall_fire": "e/e7/神吞激光墙发射.ogg",
    "dog_hurt": "2/23/吞食魔受伤.ogg",
    "dog_jump": "e/e7/吞食魔跳跃.ogg",
    "dog_seg1": "b/b9/神吞体节破碎1.ogg",
    "dog_seg2": "5/5b/神吞体节破碎2.ogg",
    "dog_seg3": "b/b9/神吞体节破碎3.ogg",
    "dog_seg4": "0/05/神吞体节破碎4.ogg",
    "dog_beam": "e/ec/神吞紫色光束.ogg",
    "dog_death": "6/65/吞食魔死亡.ogg",
}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for name, rel in WANTED.items():
        url = BASE + urllib.parse.quote(rel)
        dst = os.path.join(OUT, name + ".ogg")
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if data[:4] != b"OggS":
                print(f"  --  {name}  不是 ogg（{len(data)} 字节）")
                continue
            with open(dst, "wb") as f:
                f.write(data)
            print(f"  OK  {name:22s} {len(data)/1024:6.0f} KB")
            ok += 1
        except Exception as exc:
            print(f"  --  {name}  {type(exc).__name__}: {exc}")
    print(f"成功 {ok}/{len(WANTED)} -> {OUT}")
