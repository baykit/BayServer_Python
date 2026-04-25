import socket
import ssl
from urllib.parse import urlparse

from h2.connection import H2Connection
from h2.config import H2Configuration


def send_double_request_same_stream_raw_second(url: str):
    u = urlparse(url)
    host = u.hostname
    port = u.port or 443
    path = u.path or "/"

    # 証明書検証なし
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_alpn_protocols(["h2"])

    sock = socket.create_connection((host, port))
    ssock = ctx.wrap_socket(sock, server_hostname=host)

    if ssock.selected_alpn_protocol() != "h2":
        raise RuntimeError("HTTP/2 not negotiated via ALPN")

    h2 = H2Connection(config=H2Configuration(client_side=True))
    h2.initiate_connection()
    ssock.sendall(h2.data_to_send())

    stream_id = 1
    headers = [
        (":method", "GET"),
        (":authority", host),
        (":scheme", "https"),
        (":path", path),
    ]

    print("=== first HEADERS (normal) ===")
    h2.send_headers(stream_id=stream_id, headers=headers, end_stream=True)
    ssock.sendall(h2.data_to_send())

    # ---- ここから2回目を raw で送る（違反） ----
    print("=== second HEADERS (raw bytes, bypass h2 state machine) ===")

    # h2 が内部に持つ HPACK encoder で header block を作る
    # （内部属性なのでバージョン差あり）
    encoder = h2.encoder
    header_block = encoder.encode(headers)

    # HEADERS frame を手で組み立てる
    # Frame format:
    # Length(24) + Type(8=0x01) + Flags(END_HEADERS|END_STREAM) + R(1)+StreamID(31) + Payload
    length = len(header_block)
    frame_type = 0x01  # HEADERS
    flags = 0x04 | 0x01  # END_HEADERS(0x4) | END_STREAM(0x1)

    header = bytearray()
    header += length.to_bytes(3, "big")
    header += frame_type.to_bytes(1, "big")
    header += flags.to_bytes(1, "big")
    header += (stream_id & 0x7FFFFFFF).to_bytes(4, "big")

    ssock.sendall(bytes(header) + header_block)

    # 応答を見る
    try:
        data = ssock.recv(65535)
        if data:
            events = h2.receive_data(data)
            for ev in events:
                print(ev)
    except Exception as e:
        print("recv error:", e)

    ssock.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python rereq_same_stm.py https://localhost:2024/")
        sys.exit(1)

    send_double_request_same_stream_raw_second(sys.argv[1])
