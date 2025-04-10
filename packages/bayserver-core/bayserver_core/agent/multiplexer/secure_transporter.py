from ssl import SSLContext
from typing import List

from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.ship.ship import Ship


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


