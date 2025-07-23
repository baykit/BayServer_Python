import threading
from typing import Dict, List, Any

from bayserver_core import bayserver as bs
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.common.transporter import Transporter
from bayserver_core.common.warp_data import WarpData
from bayserver_core.common.warp_handler import WarpHandler
from bayserver_core.docker.warp import Warp
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.internet_address import InternetAddress
from bayserver_core.ship.ship import Ship


class WarpShip(Ship):

    docker: Warp
    tour_map: Dict[int, List[object]]
    host: str
    port: int
    warp_base: str
    max_ships: int
    host_addr: InternetAddress
    lock: threading.RLock
    connected: bool
    protocol_handler: ProtocolHandler
    socket_timout_sec: int

    def __init__(self):
        super().__init__()
        self.docker = None
        self.host = None
        self.port = None
        self.docker = None
        self.tour_map = {}
        self.lock = threading.RLock()
        self.protocol_handler = None
        self.connected = False
        self.cmd_buf = []

    def init_warp(self, rd: Rudder, agt_id: int, tp: Transporter, dkr: Warp, proto_hnd: ProtocolHandler):
        super().init(agt_id, rd, tp)
        self.docker = dkr
        self.socket_timeout_sec = self.docker.timeout_sec() if self.docker.timeout_sec() > 0 else bs.BayServer.harbor.socket_timeout_sec()
        self.protocol_handler = proto_hnd
        self.protocol_handler.init(self)

    def __str__(self):
        proto = ""
        if self.protocol_handler:
            proto = self.protocol_handler.protocol()
        return f"agt#{self.agent_id} wsip#{self.ship_id}/{self.object_id}[{proto}]"


    def __repr__(self):
        return self.__str__()

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        super().reset()
        if len(self.tour_map) > 0:
            BayLog.error("BUG: Some tours is active: %s", self.tour_map)

        self.tour_map = {}
        self.connected = False
        self.cmd_buf = []

    ######################################################
    # Implements Ship
    ######################################################

    def notify_handshake_done(self, proto: str) -> int:
        self.protocol_handler.verify_protocol(proto)
        return NextSocketAction.CONTINUE

    def notify_connect(self) -> int:
        self.connected = True
        for pair in self.tour_map.values():
            tur = pair[1]
            tur.check_tour_id(pair[0])
            WarpData.get(tur).start()

        return NextSocketAction.CONTINUE


    def notify_read(self, buf: bytes, adr: Any) -> int:
        return self.protocol_handler.bytes_received(buf, adr)

    def notify_eof(self) -> int:
        BayLog.debug("%s EOF detected", self)

        if len(self.tour_map) == 0:
            BayLog.debug("%s No warp tours. only close", self)
            return NextSocketAction.CLOSE

        for pair in self.tour_map.values():
            tur = pair[1]
            tur.check_tour_id(pair[0])

            try:
                if not tur.res.header_sent:
                    BayLog.debug("%s Send ServiceUnavailable: tur=%s", self, tur)
                    tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.SERVICE_UNAVAILABLE, "Server closed on reading headers")
                else:
                    # NOT treat EOF as Error
                    BayLog.debug("%s EOF is not an error: tur=%s", self, tur)
                    tur.res.end_res_content(Tour.TOUR_ID_NOCHECK)
            except IOError as e:
                BayLog.debug_e(e)

        self.tour_map.clear()
        return NextSocketAction.CLOSE

    def notify_error(self, e: Exception) -> None:
        BayLog.error_e(e, "notify_error")

    def notify_protocol_error(self, e: ProtocolException) -> bool:
        BayLog.error_e(e)
        self.notify_error_to_owner_tour(HttpStatus.SERVICE_UNAVAILABLE, e.args[0])

    def notify_close(self) -> None:
        BayLog.debug("%s notifyClose", self)
        self.notify_error_to_owner_tour(HttpStatus.SERVICE_UNAVAILABLE, f"{self} server closed")
        self.end_ship()

    def check_timeout(self, duration_sec: int) -> bool:
        if self.is_timeout(duration_sec):
            self.notify_error_to_owner_tour(HttpStatus.GATEWAY_TIMEOUT, f"{self} server timeout")
            return True
        else:
            return False


    ######################################################
    # Other methods
    ######################################################
    def init_warp(self, rd: Rudder, agt_id: int, tp: Transporter, dkr: Warp, proto_hnd: ProtocolHandler):
        self.init(agt_id, rd, tp)
        self.docker = dkr
        if self.docker.timeout_sec() >= 0:
            self.socket_timeout_sec = self.docker.timeout_sec()
        else:
            self.socket_timeout_sec = bs.BayServer.harbor.socket_timeout_sec()
        self.protocol_handler = proto_hnd
        self.protocol_handler.init(self)

    def warp_handler(self) -> WarpHandler:
        return self.protocol_handler.command_handler

    def start_warp_tour(self, tur):
        w_hnd = self.warp_handler()
        warp_id = w_hnd.next_warp_id()
        wdat = w_hnd.new_warp_data(warp_id)
        BayLog.debug("%s new warp tour related to %s", wdat, tur)
        tur.req.set_content_handler(wdat)

        BayLog.debug("%s start: warpId=%d", wdat, warp_id);
        if warp_id in self.tour_map.keys():
            raise Sink("warpId exists")

        self.tour_map[warp_id] = [tur.id(), tur]
        w_hnd.send_req_headers(tur)

        if self.connected:
            BayLog.debug("%s is already connected. Start warp tour:%s", wdat, tur);
            wdat.start()

    def end_warp_tour(self, tur):
        wdat = WarpData.get(tur)
        BayLog.debug("%s end warp tour: warp_id=%d started=%s ended=%s", tur, wdat.warp_id, wdat.started, wdat.ended)

        if self.tour_map.get(wdat.warp_id) is None:
            raise Sink("%s WarpId not in tourMap: %d", tur, wdat.warp_id)
        else:
            del self.tour_map[wdat.warp_id]
        self.docker.keep(self)

    def notify_service_unavailable(self, msg):
        self.notify_error_to_owner_tour(HttpStatus.SERVICE_UNAVAILABLE, msg)

    def get_tour(self, warp_id, must=True) -> Tour:
        pair = self.tour_map.get(warp_id)
        if pair is not None:
            tur = pair[1]
            tur.check_tour_id(pair[0])
            if not WarpData.get(tur).ended:
                return tur

        if must:
            raise Sink("%s warp tours not found: id=%d", self, warp_id)
        else:
            return None

    def packet_unpacker(self):
        return self.protocol_handler.packet_unpacker

    def notify_error_to_owner_tour(self, status, msg):
        with self.lock:
            for warp_id in self.tour_map.keys():
                tur = self.get_tour(warp_id)
                BayLog.debug("%s send error to owner: %s running=%s", self, tur, tur.is_running())
                if tur.is_running():
                    try:
                        tur.res.send_error(Tour.TOUR_ID_NOCHECK, status, msg)
                    except BaseException as e:
                        BayLog.error_e(e)
                else:
                    tur.res.end_res_content(Tour.TOUR_ID_NOCHECK)

            self.tour_map.clear()

    def end_ship(self):
        self.docker.on_end_ship(self)

    def abort(self, check_id):
        self.check_ship_id(check_id)
        self.transporter.req_close(self.rudder)

    def is_timeout(self, duration):
        if self.keeping:
            # warp connection never timeout in keeping
            timeout = False
        elif self.socket_timeout_sec <= 0:
            timeout = False

        else:
            timeout = duration >= self.socket_timeout_sec

        BayLog.debug("%s Warp check timeout: dur=%d, timeout=%s, keeping=%s limit=%d",
                     self, duration, timeout, self.keeping, self.socket_timeout_sec)
        return timeout

    def post(self, cmd, listener=None):
        if not self.connected:
            self.cmd_buf.append([cmd, listener])
        else:
            if cmd is None:
                listener()
            else:
                self.protocol_handler.command_packer.post(self, cmd, listener)

    def flush(self):
        for cmd_and_lis in self.cmd_buf:
            cmd = cmd_and_lis[0]
            lis = cmd_and_lis[1]
            if cmd is None:
                lis()
            else:
                self.protocol_handler.command_packer.post(self, cmd, lis)
        self.cmd_buf = []



