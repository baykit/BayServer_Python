from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.agent.transporter.transporter import Transporter

class UdpTransporter(Transporter):

    def __init__(self, server_mode, bufsiz):
        super().__init__(server_mode, bufsiz, False)

    def init(self, nb_hnd, ch, lis):
        super().init(nb_hnd, ch, lis)
        self.handshaked = True

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
        return self.ch.recvfrom(self.capacity)

    def write_nonblock(self, buf, adr):
        try:
            return self.ch.sendto(buf, adr)
        except BlockingIOError as e:
            BayLog.error_e(e, "%s send error: %s", self, e)
            return 0
