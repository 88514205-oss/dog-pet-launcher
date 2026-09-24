"""抓灾厄中文维基的 ogg 音效清单，并下载需要的那些。"""

import os
import re
import sys
import urllib.parse
import urllib.request

BASE = "https://calamity.huijiwiki.com"
MIME_PAGES = [
    "/index.php?title=%E7%89%B9%E6%AE%8A:MIME%E6%90%9C%E7%B4%A2&mime=application%2Fogg&limit=500",
    "/index.php?title=%E7%89%B9%E6%AE%8A:MIME%E6%90%9C%E7%B4%A2&mime=audio%2Fogg&limit=500",
]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def list_sounds():
    names = set()
    for p in MIME_PAGES:
        try:
            html = fetch(BASE + p)
        except Exception as exc:
            print("  抓取失败", p, exc)
            continue
        for m in re.findall(r'href="([^"]*?\.ogg)"', html):
            names.add(urllib.parse.unquote(m))
        for m in re.findall(r'title="([^"]*?\.ogg)"', html):
            names.add(m)
    return sorted(names)


def download(name, outdir):
    """通过 Special:FilePath 拿原始文件。"""
    url = f"{BASE}/index.php?title=%E7%89%B9%E6%AE%8A:FilePath/{urllib.parse.quote(name)}"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except Exception as exc:
        return None, str(exc)
    if not data or data[:4] not in (b"OggS", b"RIFF"):
        return None, "不是音频数据"
    os.makedirs(outdir, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", name)
    dst = os.path.join(outdir, safe)
    with open(dst, "wb") as f:
        f.write(data)
    return dst, len(data)


if __name__ == "__main__":
    if "--list" in sys.argv:
        names = list_sounds()
        print(f"共 {len(names)} 个 ogg：")
        for n in names:
            print("  ", n)
        sys.exit(0)
    wanted = sys.argv[1:]
    outdir = r"D:\SCH\DoGPet\assets\sfx"
    for n in wanted:
        dst, info = download(n, outdir)
        print(("  OK  " + os.path.basename(dst) + f"  {info/1024:.0f} KB")
              if dst else f"  --  {n}  {info}")
