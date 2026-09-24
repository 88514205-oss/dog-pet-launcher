"""抓 B站搜索页内嵌 JSON，拿到标题+BV，用来区分原版和翻奏。"""

import json
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Referer": "https://www.bilibili.com/",
      "Accept-Language": "zh-CN,zh;q=0.9"}

BAD = ("钢琴", "独奏", "翻奏", "remix", "Remix", "REMIX", "cover", "Cover",
       "8-bit", "8位", "电音", "串烧", "midi", "MIDI", "演奏", "翻弹", "改编",
       "教程", "教学", "红石", "纯音乐盒", "扒谱")
GOOD = ("原曲", "原版", "official", "Official", "OST", "原声", "官方", "DM DOKURO",
        "全曲", "主题曲", "BGM")


def clean(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = t.replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def query(kw):
    url = "https://search.bilibili.com/all?keyword=" + urllib.parse.quote(kw)
    req = urllib.request.Request(url, headers=UA)
    html = urllib.request.urlopen(req, timeout=35).read().decode("utf-8", "replace")
    out = []
    seen = set()
    for m in re.finditer(r'\{[^{}]{0,400}?"bvid":"(BV[0-9A-Za-z]{10})"[^{}]{0,400}?\}', html):
        blk = m.group(0)
        bv = m.group(1)
        if bv in seen:
            continue
        tm = re.search(r'"title":"(.*?)","', blk + ",")
        title = clean(tm.group(1)) if tm else ""
        dm = re.search(r'"duration":"?(\d+)', blk)
        if not title:
            continue
        seen.add(bv)
        out.append((bv, title, int(dm.group(1)) if dm else 0))
    if not out:
        for m in re.finditer(r'"bvid":"(BV[0-9A-Za-z]{10})"', html):
            bv = m.group(1)
            if bv in seen:
                continue
            seen.add(bv)
            out.append((bv, "(无标题)", 0))
    return out


if __name__ == "__main__":
    for kw in sys.argv[1:]:
        print(f"\n===== 搜索: {kw} =====")
        try:
            rows = query(kw)
        except Exception as exc:
            print("  失败:", type(exc).__name__, exc)
            continue
        for bv, title, dur in rows[:14]:
            bad = any(b in title for b in BAD)
            good = any(g in title for g in GOOD)
            mark = "原版?" if (good and not bad) else ("翻奏 " if bad else "  ?  ")
            print(f"  [{mark}] {bv}  {dur}s  {title[:62]}")
