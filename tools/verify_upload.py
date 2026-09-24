"""校验上传到下载页的文件是否完整。"""

import http.client
import os
import sys
import urllib.parse

HOST = "38.244.14.65"
PORT = 7878


def head(name):
    q = urllib.parse.quote(name)
    c = http.client.HTTPConnection(HOST, PORT, timeout=60)
    try:
        c.request("HEAD", "/download/" + q)
        r = c.getresponse()
        return r.status, r.getheader("Content-Length"), r.getheader("Content-Type")
    except Exception as exc:
        return None, str(exc), None
    finally:
        c.close()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        name = os.path.basename(p)
        local = os.path.getsize(p) if os.path.isfile(p) else None
        status, length, ctype = head(name)
        remote = int(length) if (length and str(length).isdigit()) else None
        mark = ""
        if local is not None and remote is not None:
            mark = "  OK 一致" if local == remote else f"  不一致! 差 {remote - local}"
        print(f"{name}\n  本地 {local}  远程 {remote}  HTTP {status}  {ctype}{mark}")
