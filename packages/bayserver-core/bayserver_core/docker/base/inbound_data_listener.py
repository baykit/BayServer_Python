from bayserver_core import bayserver as bs
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.transporter.data_listener import DataListener
from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink


class InboundDataListener(DataListener):

    def __init__(self, sip):
        self.ship = sip

    def __str__(self):
        return str(self.ship)

    ######################################################
    # Implements DataListener
    ######################################################

    def notify_handshake_done(self, protocol):
        BayLog.trace("%s notify_handshake_done: proto=%s", self, protocol)
        return NextSocketAction.CONTINUE

    def notify_connect(self):
        raise Sink("Illegal connect call")

    def notify_read(self, buf, adr):
        BayLog.debug("%s notify_read", self)
        return self.ship.protocol_handler.bytes_received(buf)

    def notify_eof(self):
        BayLog.debug("%s notify_eof", self)
        return NextSocketAction.CLOSE

    def notify_protocol_error(self, err):
        BayLog.trace("%s notify_protocol_error", self)
        if BayLog.debug_mode():
            BayLog.error_e(err)

        return self.ship.protocol_handler.send_req_protocol_error(err)

    def notify_close(self):
        BayLog.debug("%s notify_close", self)

        self.ship.abort_tours()

        if len(self.ship.active_tours) > 0:
            # cannot close because there are some running tours
            BayLog.debug("%s cannot end ship because there are some running tours (ignore)", self)
            self.ship.need_end = True
        else:
            self.ship.end_ship()


    def check_timeout(self, duration_sec):
        if self.ship.socket_timeout_sec <= 0:
            timeout = False
        elif self.ship.keeping:
            timeout = duration_sec >= bs.BayServer.harbor.keep_timeout_sec
        else:
            timeout = duration_sec >= self.ship.socket_timeout_sec

        BayLog.debug("%s Check timeout: dur=%d timeout=%s, keeping=%s, limit=%d",
                     self, duration_sec, timeout, self.ship.keeping, self.ship.socket_timeout_sec)
        return timeout

