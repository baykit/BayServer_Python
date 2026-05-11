import socket
import ssl

from bayserver_core.rudder.rudder import Rudder


class SocketRudder(Rudder):
    skt: socket.socket

    def __init__(self, skt: socket.socket):
        self.skt = skt

    def __str__(self):
        return f"SocketRudder:{self.skt}"

    def key(self) -> object:
        return self.skt

    def set_non_blocking(self) -> None:
        self.skt.setblocking(False)

    def read(self, size: int) -> bytes:
        return self.skt.recv(size)

    def write(self, data: bytes) -> int:
        return self.skt.send(data)

    def close(self) -> None:
        # Half-close the write side so the peer sees TCP FIN (and TLS
        # close_notify on SSLSocket) instead of a RST that would happen
        # if close() were called while data was still pending in the
        # receive buffer. Java's NIO SSLEngine does this automatically.
        try:
            self.skt.shutdown(socket.SHUT_WR)
        except (OSError, ssl.SSLError):
            pass
        self.skt.close()

    def closed(self) -> bool:
        return self.skt.fileno() == -1

    def fileno(self) -> int:
        return self.skt.fileno()