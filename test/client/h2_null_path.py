#!/usr/bin/env python3
import sys
import socket
import ssl
from urllib.parse import urlparse

from hpack import Encoder

CLIENT_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

FRAME_SETTINGS = 0x4
FRAME_HEADERS   = 0x1

FLAG_END_STREAM  = 0x1
FLAG_END_HEADERS = 0x4

def build_frame(frame_type: int, flags: int, stream_id: int, payload: bytes) -> bytes:
    if stream_id < 0 or stream_id > 0x7fffffff:
        raise ValueError("invalid stream_id")
    length = len(payload)
    if length > 0xFFFFFF:
        raise ValueError("payload too large")

    header = bytearray(9)
    header[0] = (length >> 16) & 0xFF
    header[1] = (length >> 8) & 0xFF
    header[2] = length & 0xFF
    header[3] = frame_type & 0xFF
    header[4] = flags & 0xFF
    header[5] = (stream_id >> 24) & 0x7F  # reserved bit must be 0
    header[6] = (stream_id >> 16) & 0xFF
    header[7] = (stream_id >> 8) & 0xFF
    header[8] = stream_id & 0xFF
    return bytes(header) + payload

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <https://host[:port]/path>", file=sys.stderr)
        sys.exit(1)

    u = urlparse(sys.argv[1])
    if u.scheme != "https":
        raise ValueError("https:// only")

    host = u.hostname
    port = u.port or 443

    # TCP
    sock = socket.create_connection((host, port))

    # TLS (insecure)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_alpn_protocols(["h2"])

    tls = ctx.wrap_socket(sock, server_hostname=host)
    if tls.selected_alpn_protocol() != "h2":
        raise RuntimeError("ALPN h2 negotiation failed")

    # 1) client preface
    tls.sendall(CLIENT_PREFACE)

    # 2) SETTINGS (empty payload is OK)
    tls.sendall(build_frame(FRAME_SETTINGS, flags=0, stream_id=0, payload=b""))

    # 3) HEADERS with NO :path
    enc = Encoder()
    headers = [
        (":method", "GET"),
        (":scheme", "https"),
        (":authority", host),
        # (":path", "/")  # 故意に送らない
    ]
    header_block = enc.encode(headers)

    stream_id = 1
    flags = FLAG_END_HEADERS | FLAG_END_STREAM
    tls.sendall(build_frame(FRAME_HEADERS, flags=flags, stream_id=stream_id, payload=header_block))

    # read some bytes and dump (server may send GOAWAY/RST_STREAM/400 etc.)
    tls.settimeout(3.0)
    try:
        data = tls.recv(65535)
        print(f"received {len(data)} bytes:")
        print(data.hex())
    except socket.timeout:
        print("no response within timeout")

    tls.close()

if __name__ == "__main__":
    main()
