"""通过 GitHub API 建仓库，并把项目文件逐个推送上去（不依赖本地 git）。"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

TOKEN_FILE = (r"C:\Users\akimi\Desktop\son-"
              r"\如果有外人打开这个并记住了这个文件的token，我就会开狂暴.txt")
ROOT = r"D:\SCH\DoGPet"
REPO = "dog-pet-launcher"

# 仓库里放什么：目录 -> 是否递归全收
INCLUDE_DIRS = ("src", "pets", "tools", "assets")
EXCLUDE_DIRS = ("assets/music", "dist", "build", "preview", "__pycache__", ".git")
EXCLUDE_EXT = (".pyc", ".spec", ".log")
INCLUDE_FILES = ("README.md", ".gitignore")
MAX_FILE = 20 * 1024 * 1024      # 单文件上限 20MB，超了的走 Release


def token():
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def api(path, tk, method="GET", data=None, raw=False):
    url = path if path.startswith("http") else "https://api.github.com" + path
    body = None
    if data is not None:
        body = data if raw else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {tk}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "DoGPet-Uploader",
    })
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            txt = r.read().decode("utf-8")
            return r.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]


def collect():
    """收集要上传的文件（相对路径 -> 本地路径）。"""
    out = {}
    for name in INCLUDE_FILES:
        p = os.path.join(ROOT, name)
        if os.path.isfile(p):
            out[name] = p
    for d in INCLUDE_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, files in os.walk(base):
            rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
            dirnames[:] = [x for x in dirnames
                           if f"{rel_dir}/{x}".lstrip("./") not in EXCLUDE_DIRS
                           and x != "__pycache__"]
            for fn in files:
                if fn.endswith(EXCLUDE_EXT):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT).replace("\\", "/")
                if any(rel.startswith(e) for e in EXCLUDE_DIRS):
                    continue
                if os.path.getsize(full) > MAX_FILE:
                    print(f"  跳过（太大，留给 Release）: {rel}")
                    continue
                out[rel] = full
    return out


if __name__ == "__main__":
    tk = token()
    st, me = api("/user", tk)
    if st != 200:
        print("token 无效:", st, me)
        sys.exit(1)
    owner = me["login"]
    print(f"账号 {owner}")

    # 1. 建仓库
    st, rp = api("/user/repos", tk, "POST", {
        "name": REPO,
        "description": "像素风桌宠启动器 · 模块化可插拔（神明吞噬者自带）",
        "private": False,
        "has_issues": True,
        "has_wiki": False,
    })
    if st == 201:
        print(f"仓库已创建: {rp['html_url']}")
    elif st == 422:
        print(f"仓库已存在: https://github.com/{owner}/{REPO}")
    else:
        print("建仓库失败:", st, rp)
        sys.exit(1)

    # 2. 逐个文件上传
    files = collect()
    print(f"待上传 {len(files)} 个文件")
    ok = fail = 0
    for i, (rel, full) in enumerate(sorted(files.items()), 1):
        with open(full, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        st, res = api(f"/repos/{owner}/{REPO}/contents/{rel}", tk, "PUT", {
            "message": f"add {rel}",
            "content": content,
            "branch": "main",
        })
        if st in (200, 201):
            ok += 1
            if i % 20 == 0 or i == len(files):
                print(f"  [{i}/{len(files)}] {rel}")
        elif st == 403 or st == 429:
            print(f"  限流，等 8 秒 ({rel})")
            time.sleep(8)
            st, res = api(f"/repos/{owner}/{REPO}/contents/{rel}", tk, "PUT", {
                "message": f"add {rel}", "content": content, "branch": "main"})
            if st in (200, 201):
                ok += 1
            else:
                fail += 1
                print(f"  失败 {rel}: {st}")
        else:
            fail += 1
            print(f"  失败 {rel}: {st} {str(res)[:120]}")
        time.sleep(0.15)
    print(f"\n完成：成功 {ok}，失败 {fail}")
    print(f"仓库地址 https://github.com/{owner}/{REPO}")
