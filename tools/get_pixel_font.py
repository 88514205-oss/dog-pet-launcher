"""下载开源中文像素字体（Zpix / Fusion Pixel）。"""

import json
import os
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
OUT = r"D:\SCH\DoGPet\assets\fonts"

REPOS = {
    "Zpix": "SolidZORO/zpix-pixel-font",
    "FusionPixel": "TakWolf/fusion-pixel-font",
}


def releases(repo):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest", headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def pick(assets, prefer):
    for a in assets:
        n = a["name"].lower()
        if prefer in n and n.endswith((".ttf", ".otf")):
            return a
    for a in assets:
        if a["name"].lower().endswith((".ttf", ".otf")):
            return a
    return None


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for tag, repo in REPOS.items():
        try:
            d = releases(repo)
        except Exception as exc:
            print(f"  --  {tag}  查 release 失败: {exc}")
            continue
        assets = d.get("assets") or []
        print(f"--- {tag}  tag={d.get('tag_name')}  资产 {len(assets)} 个 ---")
        for a in assets[:6]:
            print(f"     {a['name']}  {a['size']/1024/1024:.1f} MB")
        prefer = "monospaced-zh_hans" if tag == "FusionPixel" else ""
        a = pick(assets, prefer)
        if a is None:
            continue
        url = a["browser_download_url"]
        dst = os.path.join(OUT, a["name"])
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=120).read()
            with open(dst, "wb") as f:
                f.write(data)
            print(f"  OK  {a['name']}  {len(data)/1024/1024:.1f} MB -> {dst}")
        except Exception as exc:
            print(f"  --  下载失败 {a['name']}: {exc}")
