"""搜索 B站并抓标题，帮原版曲目从翻奏里筛出来。"""

import re
import subprocess
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

BAD = ("钢琴", "独奏", "翻奏", "remix", "Remix", "REMIX", "cover", "Cover",
       "8-bit", "8位", "电音", "串烧", "midi", "MIDI", "纯钢琴", "手风琴",
       "演奏", "翻弹", "改编", "教程", "教学", "谱", "红石")
GOOD = ("原曲", "原版", "official", "Official", "OST", "原声带", "官方",
        "DM DOKURO", "全曲", "主题曲")


def search(keyword, n=14):
    """用 yt-dlp 的进程内 API 搜索（外挂子进程抓输出会被沙箱拦）。"""
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"bilisearch{n}:{keyword}", download=False)
    out = []
    for e in (info.get("entries") or []):
        url = e.get("url") or e.get("webpage_url")
        title = e.get("title") or ""
        dur = e.get("duration")
        if url:
            out.append((title, url, dur))
    return out


def title_of(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except Exception as exc:
        return None, str(exc)
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    if not m:
        return None, "无标题"
    t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    t = t.replace("_哔哩哔哩_bilibili", "").strip()
    return t, None


if __name__ == "__main__":
    kw = sys.argv[1]
    print(f"搜索: {kw}")
    rows = search(kw)
    if not rows:
        print("  （没搜到结果）")
    for title, url, dur in rows:
        bad = any(b in title for b in BAD)
        good = any(g in title for g in GOOD)
        mark = "原版?" if (good and not bad) else ("翻奏 " if bad else "  ?  ")
        d = f"{dur}s" if dur else "?"
        print(f"  [{mark}] ({d}) {title[:66]}")
        print(f"          {url}")
