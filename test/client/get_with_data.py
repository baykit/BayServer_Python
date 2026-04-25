#!/usr/bin/env python3
import argparse
import socket
import ssl
from h2.connection import H2Connection
from h2.config import H2Configuration

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("port", type=int)
    ap.add_argument("path")
    ap.add_argument("--data", default="hello", help="DATAフレームで送るボディ")
    ap.add_argument("--insecure", action="store_true", help="証明書検証を無効化")
    args = ap.parse_args()

    # TCP
    sock = socket.create_connection((args.host, args.port))

    # TLS + ALPN(h2)
    ctx = ssl.create_default_context()
    if args.insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    ctx.set_alpn_protocols(["h2"])
    tls = ctx.wrap_socket(sock, server_hostname=args.host)

    negotiated = tls.selected_alpn_protocol()
    if negotiated != "h2":
        raise SystemExit(f"ALPN negotiation failed: {negotiated!r}")

    # HTTP/2 接続開始
    h2_config = H2Configuration(client_side=True, header_encoding="utf-8")
    conn = H2Connection(config=h2_config)
    conn.initiate_connection()
    tls.sendall(conn.data_to_send())

    # stream を開始（GET）
    stream_id = conn.get_next_available_stream_id()
    headers = [
        (":method", "GET"),
        (":scheme", "https"),
        (":authority", f"{args.host}:{args.port}"),
        (":path", args.path),
        ("content-type", "application/octet-stream"),
        ("content-length", str(len(args.data.encode("utf-8")))),
    ]

    # HEADERS は END_STREAM=False にして、後続の DATA を送る
    conn.send_headers(stream_id, headers, end_stream=False)
    tls.sendall(conn.data_to_send())

    # DATA を送って stream を閉じる（end_stream=True）
    body = args.data.encode("utf-8")
    conn.send_data(stream_id, body, end_stream=True)
    tls.sendall(conn.data_to_send())

    # 応答を読む（簡易：一定量読む）
    tls.settimeout(3)
    try:
        while True:
            data = tls.recv(65535)
            if not data:
                break
            events = conn.receive_data(data)
            for ev in events:
                # ざっくり表示（必要ならイベントごとに分岐して整形）
                print(ev)
            tls.sendall(conn.data_to_send())
    except socket.timeout:
        pass
    finally:
        tls.close()

if __name__ == "__main__":
    main()
