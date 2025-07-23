import socket

from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.sink import Sink


class UdpSocketRudder(SocketRudder):

    def __init__(self, skt: socket.socket):
        super().__init__(skt)

    def __str__(self):
        return f"UdpSocketRudder:{self.skt}"

    def read(self, size: int) -> bytes:
        # read not supported
        raise Sink()

    def write(self, data: bytes) -> int:
        # write not supported
        raise Sink()