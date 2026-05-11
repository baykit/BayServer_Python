from ssl import SSLContext
from typing import List

from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.ship.ship import Ship
from bayserver_core.sink import Sink
from bayserver_core.util.data_consume_listener import DataConsumeListener


class SecureTransporter(PlainTransporter):

    sslctx: SSLContext

    def __init__(self, mpx: Multiplexer, sip: Ship, server_mode: bool, bufsize: int, trace_ssl: bool,  sslctx: SSLContext, app_protocols: List[str]):
        super().__init__(mpx, sip, server_mode, bufsize, trace_ssl)
        self.sslctx = sslctx


        #self.ssl_socket = None


    def __str__(self):
        return f"stp[{self.ship}]"


    ######################################################
    # Implements Transporter
    ######################################################

    def is_secure(self):
        return True

    def req_transfer(self, rd: Rudder, file_rd: Rudder, ofs: int, length: int, listener: DataConsumeListener) -> None:
        # Direct Boarding (sendfile) is incompatible with TLS framing.
        raise Sink()


