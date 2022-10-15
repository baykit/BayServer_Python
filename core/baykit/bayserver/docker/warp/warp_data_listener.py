from baykit.bayserver.agent.transporter.data_listener import DataListener
from baykit.bayserver.agent.next_socket_action import NextSocketAction
from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.docker.warp.warp_data import WarpData
from baykit.bayserver.tour.tour import Tour
from baykit.bayserver.util.http_status import HttpStatus
from baykit.bayserver.util.sys_util import SysUtil


class WarpDataListener(DataListener):

    def __init__(self, sip):
        super().__init__()
        self.ship = sip

    def __str__(self):
        return str(self.ship)

    def __repr__(self):
        return self.__str__()

    ######################################################
    # Implements DataListener
    ######################################################

    def notify_handshake_done(self, protocol):
        self.ship.protocol_handler.verify_protocol(protocol)

        #  Send pending packet
        self.ship.agent.non_blocking_handler.ask_to_write(self.ship.socket)
        return NextSocketAction.CONTINUE

    def notify_connect(self):
        self.ship.connected = True

        if SysUtil.run_on_windows():
            # Check connected by sending 0 bytes data
            buf = b""
            self.ship.socket.send(buf)

        for pair in self.ship.tour_map.values():
            tur = pair[1]
            tur.check_tour_id(pair[0])
            WarpData.get(tur).start()

        return NextSocketAction.WRITE

    def notify_eof(self):
        BayLog.debug("%s EOF detected", self)

        if len(self.ship.tour_map) == 0:
            BayLog.debug("%s No warp tours. only close", self)
            return NextSocketAction.CLOSE

        for warp_id in self.ship.tour_map.keys():
            pair = self.ship.tour_map[warp_id]
            tur = pair[1]
            tur.check_tour_id(pair[0])

            if not tur.res.header_sent:
                BayLog.debug("%s Send ServiceUnavailable: tur=%s", self, tur)
                tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.SERVICE_UNAVAILABLE, "Server closed on reading headers")
            else:
                # NOT treat EOF as Error
                BayLog.debug("%s EOF is not an error: tur=%s", self, tur)
                tur.res.end_content(Tour.TOUR_ID_NOCHECK)

        self.ship.tour_map.clear()
        return NextSocketAction.CLOSE

    def notify_read(self, buf, adr):
        return self.ship.protocol_handler.bytes_received(buf)

    def notify_protocol_error(self, err):
        BayLog.error_e(err)
        self.ship.notify_error_to_owner_tour(HttpStatus.SERVICE_UNAVAILABLE, err.args[0])
        return True

    def check_timeout(self, duration_sec):
        if self.ship.is_timeout(duration_sec):
            self.ship.notify_error_to_owner_tour(HttpStatus.GATEWAY_TIMEOUT, f"{self} server timeout")
            return True
        else:
            return False

    def notify_close(self):
        BayLog.debug("%s notifyClose", self)
        self.ship.notify_error_to_owner_tour(HttpStatus.SERVICE_UNAVAILABLE, f"{self} server closed")
        self.ship.end_ship()

