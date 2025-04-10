import socket

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
        self.skt.close()

    def closed(self) -> bool:
        return self.skt.fileno() == -1