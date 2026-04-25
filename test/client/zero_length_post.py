#!/usr/bin/env python3
import argparse
import urllib.parse
import sys

# ---------------------------
# HTTP/1.1
# ---------------------------
def post_http11(url, use_https, insecure):
    import http.client
    import ssl

    u = urllib.parse.urlparse(url)
    host = u.hostname
    port = u.port or (443 if use_https else 80)
    path = u.path or "/"
    if u.query:
        path += "?" + u.query

    context = None
    if use_https:
        if insecure:
            context = ssl._create_unverified_context()
        else:
            context = ssl.create_default_context()

    conn_cls = http.client.HTTPSConnection if use_https else http.client.HTTPConnection
    conn = conn_cls(host, port, timeout=10, context=context)

    try:
        conn.request("POST", path, body=b"", headers={"Content-Length": "0"})
        resp = conn.getresponse()
        print(f"HTTP/1.1 {resp.status} {resp.reason}")
        print(resp.read().decode(errors="replace"))
    finally:
        conn.close()


# ---------------------------
# HTTP/2
# ---------------------------
def post_http2(url, insecure):
    import httpx

    with httpx.Client(http2=True, verify=not insecure, timeout=10) as client:
        r = client.post(url, content=b"", headers={"Content-Length": "0"})
        print(f"HTTP/2 {r.status_code}")
        print(r.text)


# ---------------------------
# HTTP/3
# ---------------------------
def post_http3(url, insecure):
    import asyncio
    from aioquic.asyncio.client import connect
    from aioquic.h3.connection import H3_ALPN
    from aioquic.h3.events import HeadersReceived, DataReceived
    import ssl

    u = urllib.parse.urlparse(url)
    if u.scheme != "https":
        raise RuntimeError("HTTP/3 requires https URL")

    async def run():
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        async with connect(
            u.hostname,
            u.port or 443,
            alpn_protocols=H3_ALPN,
            ssl=ctx,
        ) as client:
            h3 = client._http
            stream_id = h3.get_next_available_stream_id()

            h3.send_headers(
                stream_id,
                [
                    (b":method", b"POST"),
                    (b":scheme", b"https"),
                    (b":authority", u.hostname.encode()),
                    (b":path", (u.path or "/").encode()),
                    (b"content-length", b"0"),
                ],
                end_stream=True,
            )
            client.transmit()

            while True:
                event = await client.wait_for_event()
                if isinstance(event, HeadersReceived):
                    print("HTTP/3 HEADERS:")
                    for k, v in event.headers:
                        print(f"{k.decode()}: {v.decode()}")
                elif isinstance(event, DataReceived):
                    print(event.data.decode(errors="replace"))
                    break

    asyncio.run(run())


# ---------------------------
# main
# ---------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--proto", choices=["http", "https"], default="http")
    parser.add_argument("--version", choices=["1.1", "2", "3"], default="1.1")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    args = parser.parse_args()

    if args.version == "1.1":
        post_http11(args.url, args.proto == "https", args.insecure)
    elif args.version == "2":
        post_http2(args.url, args.insecure)
    elif args.version == "3":
        post_http3(args.url, args.insecure)
    else:
        raise AssertionError


if __name__ == "__main__":
    main()
