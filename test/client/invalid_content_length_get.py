import sys
import time
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

    headers = {
        "Content-Length": "2"
    }
    body = b"ABCD"  # 実際は4バイト送信

    print(f"Sending GET to {scheme}://{host}:{port}{path}")
    print(f"Headers: {headers}")
    print(f"Body length: {len(body)}")

    conn.request("GET", path, body=body, headers=headers)

    response = conn.getresponse()
    print("Status:", response.status)
    print("Reason:", response.reason)
    print("Response body:", response.read())

    print("Keeping connection open for 120 seconds...")
    time.sleep(120)
    # conn.close() なし

if __name__ == "__main__":
    main()
