from typing import Any

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.common.read_only_ship import ReadOnlyShip
from bayserver_core.common.transporter import Transporter
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus


class SendFileShip(ReadOnlyShip):

    file_wrote_len: int
    tour: Tour
    tour_id: int
    path: str
    abortable: bool

    def __init__(self):
        super().__init__()
        self.reset()

    def init(self, rd: Rudder, tp: Transporter, tur: Tour):
        super().init(tur.ship.agent_id, rd, tp)
        self.file_wrote_len = 0
        self.tour = tur
        self.tour_id = tur.tour_id

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        super().reset()

        self.file_wrote_len = 0
        self.tour_id = -1
        self.tour = None


    ######################################################
    # Implements ReqContentHandler
    ######################################################

    def notify_read(self, buf: bytes, adr: Any) -> int:
        self.file_wrote_len += len(buf)
        BayLog.debug("%s read file %d bytes: total=%d", self, len(buf), self.file_wrote_len)

        try:
            available = self.tour.res.send_res_content(self.tour_id, buf, 0, len(buf))
            if available:
                return NextSocketAction.CONTINUE
            else:
                return NextSocketAction.SUSPEND

        except IOError as e:
            self.notify_error(e)
            return NextSocketAction.CLOSE

    def notify_error(self, e: Exception) -> None:
        BayLog.debug_e(e, "%s Error notified", self)
        try:
            self.tour.res.send_error(self.tour_id, HttpStatus.INTERNAL_SERVER_ERROR, None, e)
        except IOError as ex:
            BayLog.debug_e(ex)


    def notify_eof(self) -> int:
        BayLog.debug("%s EOF", self)
        try:
            self.tour.res.end_res_content(self.tour_id)
        except IOError as ex:
            BayLog.debug_e(ex)
        return NextSocketAction.CLOSE

    def notify_close(self) -> None:
        BayLog.debug("%s Close", self)

    def check_timeout(self, duration_sec: int) -> bool:
        return False

