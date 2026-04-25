#!/usr/bin/env python3
"""
HTTP/2 クライアント:
- URL を1つ受け取る
- GET
- Content-Length を送らない
- payload長0の DATA フレームを送る
"""

import argparse
import socket
import ssl
import sys
from urllib.parse import urlparse

from h2.connection import H2Connection
from h2.config import H2Configuration
from h2.events import (
    ResponseReceived,
    DataReceived,
    StreamEnded,
    StreamReset,
)


def parse_url(url: str):
    u = urlparse(url)
    if u.scheme != "https":
        raise ValueError("URL must start with https://")

    host = u.hostname
    port = u.port or 443
    path = u.path or "/"
    if u.query:
        path += "?" + u.query

    return host, port, path


def connect_h2(host: str, port: int, insecure: bool, timeout: float) -> ssl.SSLSocket:
    raw = socket.create_connection((host, port), timeout=timeout)

    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    ctx.set_alpn_protocols(["h2"])
    tls = ctx.wrap_socket(raw, server_hostname=host)

    if tls.selected_alpn_protocol() != "h2":
        raise RuntimeError("ALPN negotiation failed (h2 not selected)")

    tls.settimeout(timeout)
    return tls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="https://host:port/path")
    ap.add_argument("--insecure", action="store_true", help="証明書検証を無効化")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--timeout", type=float, default=3.0)
    ap.add_argument("--empty-data-frames", type=int, default=1)
    args = ap.parse_args()

    host, port, path = parse_url(args.url)

    tls = connect_h2(host, port, args.insecure, args.timeout)

    conn = H2Connection(
        config=H2Configuration(client_side=True, header_encoding="utf-8")
    )
    conn.initiate_connection()
    tls.sendall(conn.data_to_send())

    stream_id = conn.get_next_available_stream_id()

    headers = [
        (":method", "GET"),
        (":scheme", "https"),
        (":authority", f"{host}:{port}"),
        (":path", path),
    ]

    # HEADERS（END_STREAM=False）
    conn.send_headers(stream_id, headers, end_stream=False)
    tls.sendall(conn.data_to_send())

    # 空 DATA フレームを送る
    for i in range(args.empty_data_frames):
        end_stream = (i == args.empty_data_frames - 1)
        conn.send_data(stream_id, b"", end_stream=end_stream)
        tls.sendall(conn.data_to_send())

    # 応答を読む
    while True:
        try:
            data = tls.recv(65535)
        except socket.timeout:
            break

        if not data:
            break

        events = conn.receive_data(data)
        for ev in events:
            if args.verbose:
                print(f"[event] {ev!r}", file=sys.stderr)

            if isinstance(ev, ResponseReceived):
                print("=== response headers ===")
                for k, v in ev.headers:
                    print(f"{k}: {v}")
                print()

            elif isinstance(ev, DataReceived):
                sys.stdout.buffer.write(ev.data)
                conn.acknowledge_received_data(
                    ev.flow_controlled_length, ev.stream_id
                )

            elif isinstance(ev, StreamReset):
                print(f"RST_STREAM: {ev.error_code}", file=sys.stderr)
                return

            elif isinstance(ev, StreamEnded):
                return

        out = conn.data_to_send()
        if out:
            tls.sendall(out)


if __name__ == "__main__":
    main()
