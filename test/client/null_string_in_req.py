import socket
import sys
import urllib.parse
import http.client


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <url>")
        sys.exit(1)

    url = sys.argv[1]
    parsed = urllib.parse.urlparse(url)

    scheme = parsed.scheme
    host = parsed.hostname
    port = parsed.port
    path = parsed.path or "/"

    if not scheme or not host:
        print("Invalid URL. Must include scheme (http/https) and host.")
        sys.exit(1)

    if port is None:
        port = 443 if scheme == "https" else 80

    if scheme == "https":
        conn = http.client.HTTPSConnection(host, port)
    elif scheme == "http":
        conn = http.client.HTTPConnection(host, port)
    else:
        print("Unsupported scheme:", scheme)
        sys.exit(1)

    # body のパラメータにヌル文字を含める
    # 例: param=hello\x00world
    body = "param=hello\x00world"

    request = (
        f"POST {path}\x00hoge.cgi HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{body}"
    )

    print("=== sending raw request ===")
    print(repr(request))

    with socket.create_connection((host, port)) as sock:
        sock.sendall(request.encode("latin-1", errors="ignore"))
        resp = sock.recv(4096)
        print("=== response ===")
        print(resp.decode("latin-1", errors="replace"))

if __name__ == "__main__":
    main()
