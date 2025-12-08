import sys
import socket
from urllib.parse import urlparse

# ---------------------------------------
# 使い方:
#   python3 send_bad_method.py http://127.0.0.1:8080/test
# ---------------------------------------

if len(sys.argv) < 2:
    print("usage: python3 send_bad_method.py <url>")
    sys.exit(1)

url = urlparse(sys.argv[1])

host = url.hostname
port = url.port or (443 if url.scheme == "https" else 80)
path = url.path or "/"

# クエリは送らず、パスだけ使用（必要なら追加可）
# path = url.path + ("?" + url.query if url.query else "")

# リクエストに使用する「異常に長いメソッド」
METHOD = (
    "method=data%5Bwp-refresh-post-lock%5D%5Bpost_id%5D=1867"
    "&data%5Bwp-refresh-post-lock%5D%5Block%5D=1753786641%3A1"
    "&data%5Bwp-refresh-post-nonces%5D%5Bpost_id%5D=1867"
    "&interval=10&_nonce=8724350ab8&action=heartbeat"
    "&screen_id=wpdmpro&has_focus=false\xffPOST"
)

# HTTP リクエストを手で構築する（生ソケット向け）
request = (
    f"{METHOD} {path} HTTP/1.1\r\n"
    f"Host: {host}\r\n"
    "Connection: close\r\n"
    "\r\n"
)

print("=== Sending malformed request ===")
print(repr(request))

# TCP 接続して送信
with socket.create_connection((host, port)) as sock:
    sock.sendall(request.encode("latin-1", errors="strict"))

    print("=== Response ===")
    # 4096 ずつ受信
    while True:
        data = sock.recv(4096)
        if not data:
            break
        print(data.decode("latin-1", errors="replace"))
