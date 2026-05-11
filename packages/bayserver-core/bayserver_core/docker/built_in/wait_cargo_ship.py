import traceback
from typing import List

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.common.read_only_ship import ReadOnlyShip
from bayserver_core.common.transporter import Transporter
from bayserver_core.http_exception import HttpException
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.tour.content_consume_listener import content_consume_listener_dev_null
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.internet_address import InternetAddress


class WaitCargoShip(ReadOnlyShip):
    """Java WaitCargoShip port. Holds a request blocked while another tour is
    populating the shared cargo, and serves it from cache when notified."""

    def __init__(self):
        super().__init__()
        self.cargo = None
        self.club = None
        self.tour = None
        self.tour_id = 0

    def init(self, rd: Rudder, tp: Transporter, tur: Tour, cgo, clb):
        super().init(tur.ship.agent_id, rd, tp)
        self.tour = tur
        self.tour_id = tur.tour_id
        self.cargo = cgo
        self.club = clb

    def __str__(self):
        return f"agt#{self.agent_id} wait_file#{self.ship_id}/{self.object_id}"

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        super().reset()
        self.tour_id = 0
        self.tour = None
        self.cargo = None
        self.club = None

    ######################################################
    # Implements ReadOnlyShip
    ######################################################

    def notify_read(self, buf: bytes, adr: InternetAddress) -> int:
        BayLog.debug("%s cargo load completed", self.tour)
        try:
            if self.cargo.exceeded():
                BayLog.debug("%s cargo exceeded", self.tour)
                self.club.arrive(self.tour)
            else:
                self.tour.res.set_res_consume_listener(content_consume_listener_dev_null)
                self._send_cargo_on_board()
        except HttpException as e:
            try:
                self.tour.res.send_error(Tour.TOUR_ID_NOCHECK, e.status, str(e))
            except IOError as ex:
                self.notify_error(ex, traceback.format_stack())
                return NextSocketAction.CLOSE

        self.cargo.release_rudder(self.rudder)
        return NextSocketAction.CONTINUE

    def notify_error(self, e: Exception, stk: List[str]) -> None:
        BayLog.debug_e(e, stk, "%s Error notified", self.tour)
        try:
            self.tour.res.send_error(self.tour_id, HttpStatus.INTERNAL_SERVER_ERROR, None, e, stk)
        except IOError as ex:
            BayLog.debug_e(ex, traceback.format_stack())

    def notify_eof(self) -> int:
        raise Sink()

    def notify_close(self) -> None:
        pass

    def check_timeout(self, duration_sec: int) -> bool:
        return False

    ######################################################
    # Private methods
    ######################################################

    def _send_cargo_on_board(self):
        self.tour.res.set_res_consume_listener(content_consume_listener_dev_null)
        self.cargo.headers().copy_to(self.tour.res.headers)
        try:
            self.tour.res.send_res_headers(Tour.TOUR_ID_NOCHECK)
            self.tour.res.send_res_content(Tour.TOUR_ID_NOCHECK, self.cargo.content(), 0, self.cargo.length())
            self.tour.res.end_res_content(Tour.TOUR_ID_NOCHECK)
        except IOError as e:
            BayLog.error_e(e, traceback.format_stack())
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, self.cargo.path())
