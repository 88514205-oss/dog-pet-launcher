"""用桌面上的 token 查 GitHub 账号与仓库情况。"""

import json
import urllib.error
import urllib.request

TOKEN_FILE = (r"C:\Users\akimi\Desktop\son-"
              r"\如果有外人打开这个并记住了这个文件的token，我就会开狂暴.txt")


def token():
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def api(path, tk, method="GET", data=None):
    url = path if path.startswith("http") else "https://api.github.com" + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {tk}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "DoGPet-Uploader",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return e.code, detail


if __name__ == "__main__":
    tk = token()
    print(f"token 长度 {len(tk)}  前缀 {tk[:4]}***  后缀 ***{tk[-2:]}")
    st, me = api("/user", tk)
    if st != 200:
        print("认证失败:", st, me)
        raise SystemExit(1)
    print(f"账号: {me.get('login')}  ({me.get('name') or '-'})")
    print(f"公开仓库 {me.get('public_repos')}  私有仓库 {me.get('total_private_repos')}")
    st, scopes = api("/", tk)
    req = urllib.request.Request("https://api.github.com/user", headers={
        "Authorization": f"Bearer {tk}", "User-Agent": "x"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("Token 权限范围:", r.headers.get("x-oauth-scopes") or "(未标注)")
    st, repos = api("/user/repos?per_page=100&sort=updated", tk)
    if st == 200:
        print(f"\n仓库列表 ({len(repos)}):")
        for rp in repos[:25]:
            print(f"  {rp['name']:<32} {'私有' if rp['private'] else '公开'}  "
                  f"{rp.get('size', 0)}KB  {rp.get('description') or ''}")
