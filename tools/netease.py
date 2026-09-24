"""从网易云搜索并尝试下载曲目（外链 mp3）。"""

import json
import os
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Referer": "https://music.163.com/",
      "Cookie": "appver=2.0.2; os=pc"}

OUT = r"D:\SCH\DoGPet\assets\music"


def api_search(keyword, limit=15):
    url = ("https://music.163.com/api/search/get/?s=" + urllib.parse.quote(keyword)
           + f"&type=1&limit={limit}&offset=0")
    req = urllib.request.Request(url, headers=UA)
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    out = []
    for s in (data.get("result") or {}).get("songs") or []:
        out.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "artists": "/".join(a.get("name", "") for a in (s.get("artists") or [])),
            "album": (s.get("album") or {}).get("name", ""),
            "duration": round((s.get("duration") or 0) / 1000),
        })
    return out


def fetch_song(song_id):
    url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            ctype = r.headers.get("Content-Type", "")
            data = r.read()
        return data, ctype
    except Exception as exc:
        return None, str(exc)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    if mode == "search":
        for kw in sys.argv[2:]:
            print(f"\n===== {kw} =====")
            try:
                for s in api_search(kw):
                    print(f"  id={s['id']:<12} {s['duration']:>4}s  {s['name'][:40]:40s} "
                          f"| {s['artists'][:22]}")
            except Exception as exc:
                print("  失败:", type(exc).__name__, exc)
    else:
        os.makedirs(OUT, exist_ok=True)
        for spec in sys.argv[2:]:
            sid, name = spec.split("=", 1)
            data, info = fetch_song(sid)
            if data is None or len(data) < 20000:
                print(f"  --  {name}  拿不到（{info if data is None else str(len(data))+' 字节'}）")
                continue
            dst = os.path.join(OUT, name + ".mp3")
            with open(dst, "wb") as f:
                f.write(data)
            print(f"  OK  {name}  {len(data)/1024/1024:.1f} MB  ->  {dst}")
