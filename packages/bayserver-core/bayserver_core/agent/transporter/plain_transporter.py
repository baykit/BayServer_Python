import socket

from bayserver_core.sink import Sink
from bayserver_core.agent.transporter.transporter import Transporter

class PlainTransporter(Transporter):
    def __init__(self, server_mode, bufsiz, write_only=False):
        super().__init__(server_mode, bufsiz, False, write_only)

    def init(self, nb_hnd, ch, lis):
        super().init(nb_hnd, ch, lis)
        self.handshaked = True  # plain socket doesn't need to handshake

    def __str__(self):
        return f"tp[{self.data_listener}]"

    ######################################################
    # Implements Transporter
    ######################################################

    def secure(self):
        return False

    def handshake_nonblock(self):
        raise Sink("needless to handshake")

    def handshake_finished(self):
        raise Sink("needless to handshake")

    def read_nonblock(self):
        if isinstance(self.ch, socket.socket):
            return (self.ch.recv(self.capacity), None)
        else:
            return (self.ch.read(self.capacity), None)

    def write_nonblock(self, buf, adr):
        if isinstance(self.ch, socket.socket):
            return self.ch.send(buf)
        else:
            return self.ch.write(buf)
