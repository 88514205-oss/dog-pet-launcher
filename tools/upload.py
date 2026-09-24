"""上传文件到 LCE 文件传输终端（http://38.244.14.65:7878/upload）。"""

import http.client
import os
import sys
import time
import uuid

HOST = "38.244.14.65"
PORT = 7878
FIELD = "file"


def upload(path):
    if not os.path.isfile(path):
        print("文件不存在:", path)
        return False
    name = os.path.basename(path)
    size = os.path.getsize(path)
    print(f"上传 {name}  {size/1024/1024:.1f} MB -> http://{HOST}:{PORT}/upload")
    with open(path, "rb") as f:
        data = f.read()

    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{FIELD}"; filename="{name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + data + tail

    t0 = time.time()
    conn = http.client.HTTPConnection(HOST, PORT, timeout=1200)
    try:
        conn.request("POST", "/upload", body=body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Connection": "close",
        })
        resp = conn.getresponse()
        content = resp.read().decode("utf-8", "replace")
    except Exception as exc:
        print("传输失败:", exc)
        return False
    finally:
        conn.close()

    dt = time.time() - t0
    print(f"HTTP {resp.status} {resp.reason}   耗时 {dt:.1f}s   "
          f"平均 {size/1024/1024/max(dt,0.01):.2f} MB/s")
    print("--- 服务器返回 ---")
    print(content[:1200])
    return 200 <= resp.status < 400


if __name__ == "__main__":
    ok = True
    for p in sys.argv[1:]:
        ok = upload(p) and ok
    sys.exit(0 if ok else 1)
