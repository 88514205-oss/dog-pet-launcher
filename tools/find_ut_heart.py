"""找 UT 原版心脏素材：查开源 UT 引擎仓库的文件树。"""

import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}

REPOS = [
    "undergroundengine/Under-Ground-Engine",
    "ZengXiaoPi/Determination-Site",
]


def tree(repo):
    for ref in ("HEAD", "main", "master"):
        url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
        try:
            req = urllib.request.Request(url, headers=UA)
            d = json.loads(urllib.request.urlopen(req, timeout=35).read().decode("utf-8"))
            return d.get("tree") or []
        except Exception as exc:
            last = exc
    print(f"  {repo}: 查不到 ({last})")
    return []


if __name__ == "__main__":
    KW = ("heart", "soul", "spr_heart")
    for repo in REPOS:
        print(f"--- {repo} ---")
        items = tree(repo)
        print(f"    条目 {len(items)}")
        hit = [it for it in items
               if it.get("type") == "blob"
               and any(k in it["path"].lower() for k in KW)
               and it["path"].lower().endswith((".png", ".gif", ".bmp", ".jpg"))]
        for it in hit[:40]:
            print(f"    {it['size']:>8}  {it['path']}")
        if not hit:
            print("    （没找到 heart/soul 图片）")
