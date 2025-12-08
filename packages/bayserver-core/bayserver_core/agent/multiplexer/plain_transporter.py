import traceback
from typing import List

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.upgrade_exception import UpgradeException
from bayserver_core.bay_log import BayLog
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.transporter import Transporter
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.ship.ship import Ship
from bayserver_core.sink import Sink
from bayserver_core.util.data_consume_listener import DataConsumeListener


class PlainTransporter(Transporter):

    multiplexer: Multiplexer
    server_mode: bool
    trace_ssl: bool
    read_buffer_size: int
    ship: Ship
    closed: bool

    def __init__(self, mpx: Multiplexer, sip: Ship, server_mode: bool, bufsiz: int, trace_ssl: bool):
        self.multiplexer = mpx
        self.ship = sip
        self.server_mode = server_mode
        self.trace_ssl = trace_ssl
        self.read_buffer_size = bufsiz
        self.closed = False

    def init(self):
        pass

    def __str__(self):
        return f"tp[{self.ship}]"

    ######################################################
    # Implements Transporter
    ######################################################

    def is_secure(self) -> bool:
        return False

    def on_connected(self, rd: Rudder) -> int:
        self.check_rudder(rd)
        return self.ship.notify_connect()

    def on_read(self, rd: Rudder, buf: bytes, adr: str) -> int:
        BayLog.debug("%s onRead", self)
        self.check_rudder(rd)

        if len(buf) == 0:
            return self.ship.notify_eof()

        else:
            try:
                return self.ship.notify_read(buf, adr)
            except UpgradeException as e:
                BayLog.debug("%s Protocol upgrade", self.ship)
                return self.ship.notify_read(buf, adr)

            except ProtocolException as e:
                close = self.ship.notify_protocol_error(e, traceback.format_stack())

                if not close and self.server_mode:
                    return NextSocketAction.CONTINUE

                else:
                    return NextSocketAction.CLOSE

            except IOError as e:
                # IOError which occur in notifyRead must be distinguished from
                # IOError which occur in handshake or readNonBlock.
                self.on_error(rd, e, traceback.format_stack())
                return NextSocketAction.CLOSE


    def on_error(self, rd: Rudder, e: BaseException, stk: List[str]) -> None:
        self.check_rudder(rd)
        self.ship.notify_error(e, stk)

    def on_closed(self, rd: Rudder) -> None:
        BayLog.debug("%s onClosed", self)
        self.check_rudder(rd)
        self.ship.notify_close()

    def req_connect(self, rd: Rudder, adr: str) -> None:
        self.check_rudder(rd)
        self.multiplexer.req_connect(rd, adr)

    def req_read(self, rd: Rudder) -> None:
        self.check_rudder(rd)
        self.multiplexer.req_read(rd)

    def req_write(self, rd: Rudder, data: bytearray, adr: str, tag: any, listener: DataConsumeListener) -> None:
        self.check_rudder(rd)
        self.multiplexer.req_write(rd, data, adr, tag, listener)

    def req_close(self, rd: Rudder) -> None:
        self.check_rudder(rd)
        self.closed = True
        self.multiplexer.req_close(rd)

    def check_timeout(self, rd: Rudder, duration_sec: int) -> bool:
        self.check_rudder(rd)
        return self.ship.check_timeout(duration_sec)

    def get_read_buffer(self) -> int:
        return self.read_buffer_size

    def print_usage(self, indent: int) -> None:
        pass

    ######################################################
    # Custom methods
    ######################################################

    def check_rudder(self, rd: Rudder):
        if rd != self.ship.rudder:
            raise Sink("Invalid rudder: %s", rd)