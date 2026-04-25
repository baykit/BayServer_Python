#!/usr/bin/env python3
import argparse
import socket
import ssl
import struct
import sys
from urllib.parse import urlparse

from hpack import Encoder

CLIENT_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

# Frame types (RFC 7540)
FT_DATA = 0x0
FT_HEADERS = 0x1
FT_SETTINGS = 0x4
FT_PING = 0x6
FT_GOAWAY = 0x7
FT_WINDOW_UPDATE = 0x8
FT_CONTINUATION = 0x9

# Flags
FLAG_END_STREAM = 0x1
FLAG_END_HEADERS = 0x4


def build_frame(frame_type, flags, stream_id, payload):
    if stream_id < 0 or stream_id > 0x7FFFFFFF:
        raise ValueError("stream_id out of range")
    length = len(payload)
    if length > 0xFFFFFF:
        raise ValueError("payload too large")

    header = struct.pack("!I", length)[1:] + bytes([frame_type, flags]) + struct.pack("!I", stream_id & 0x7FFFFFFF)
    return header + payload


def build_settings_frame():
    # empty SETTINGS
    return build_frame(FT_SETTINGS, 0x0, 0, b"")


def build_headers_and_continuation(stream_id, headers, split_at=8):
    """
    HPACKでヘッダブロックを作り、HEADERS(END_HEADERS=0) と
    CONTINUATION(END_HEADERS=1) に分割して送る。
    """
    enc = Encoder()
    header_block = enc.encode(headers)

    if len(header_block) <= 1:
        raise RuntimeError("header block too small; cannot split")

    if len(header_block) <= split_at:
        split_at = max(1, len(header_block) // 2)

    part1 = header_block[:split_at]
    part2 = header_block[split_at:]

    headers_frame = build_frame(
        FT_HEADERS,
        flags=FLAG_END_STREAM,  # GETでリクエストボディなし
        stream_id=stream_id,
        payload=part1           # END_HEADERS は立てない
    )

    continuation_frame = build_frame(
        FT_CONTINUATION,
        flags=FLAG_END_HEADERS,  # ここでヘッダブロック完了
        stream_id=stream_id,
        payload=part2
    )

    return headers_frame, continuation_frame


def recv_and_dump_some_frames(sock, max_bytes=65535):
    try:
        data = sock.recv(max_bytes)
    except socket.timeout:
        return
    if not data:
        return

    i = 0
    while i + 9 <= len(data):
        length = int.from_bytes(data[i:i+3], "big")
        ftype = data[i+3]
        flags = data[i+4]
        sid = int.from_bytes(data[i+5:i+9], "big") & 0x7FFFFFFF
        i += 9
        if i + length > len(data):
            break
        payload = data[i:i+length]
        i += length

        name_map = {
            FT_DATA: "DATA",
            FT_HEADERS: "HEADERS",
            FT_SETTINGS: "SETTINGS",
            FT_PING: "PING",
            FT_GOAWAY: "GOAWAY",
            FT_WINDOW_UPDATE: "WINDOW_UPDATE",
            FT_CONTINUATION: "CONTINUATION",
        }
        name = name_map.get(ftype, "TYPE_%d" % ftype)

        print("<- %s stream=%d len=%d flags=0x%02x" % (name, sid, length, flags))
        if ftype == FT_DATA and payload:
            sys.stdout.buffer.write(payload[:1024])
            sys.stdout.buffer.flush()


def run(url, timeout=5.0):
    u = urlparse(url)
    scheme = (u.scheme or "").lower()
    if scheme not in ("https", "http"):
        print("Only http:// or https:// are supported.", file=sys.stderr)
        return 2

    host = u.hostname
    if not host:
        print("Invalid URL (no host).", file=sys.stderr)
        return 2

    port = u.port or (443 if scheme == "https" else 80)
    path = u.path or "/"
    if u.query:
        path += "?" + u.query

    raw = socket.create_connection((host, port), timeout=timeout)

    if scheme == "https":
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_alpn_protocols(["h2"])
        sock = ctx.wrap_socket(raw, server_hostname=host)
        if sock.selected_alpn_protocol() != "h2":
            print("ALPN did not negotiate 'h2'.", file=sys.stderr)
            sock.close()
            return 2
    else:
        sock = raw  # h2c prior knowledge

    sock.settimeout(timeout)

    sock.sendall(CLIENT_PREFACE)
    sock.sendall(build_settings_frame())

    authority = host if (u.port is None) else "%s:%d" % (host, port)
    headers = [
        (":method", "GET"),
        (":scheme", scheme),
        (":authority", authority),
        (":path", path),
        ("user-agent", "continuation-demo/0.1"),
        ("accept", "*/*"),
    ]

    stream_id = 1
    h, c = build_headers_and_continuation(stream_id, headers, split_at=8)
    sock.sendall(h)
    sock.sendall(c)

    recv_and_dump_some_frames(sock)
    sock.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="Target URL (https://... recommended)")
    args = ap.parse_args()
    raise SystemExit(run(args.url))


if __name__ == "__main__":
    main()
