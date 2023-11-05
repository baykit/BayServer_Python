import threading

from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog
from bayserver_core.docker.warp.warp_data import WarpData
from bayserver_core.sink import Sink
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.watercraft.ship import Ship


class WarpShip(Ship):

    def __init__(self):
        super().__init__()
        self.docker = None
        self.socket_timeout_sec = None
        self.tour_map = {}
        self.lock = threading.RLock()
        self.connected = False
        self.cmd_buf = []

    def __str__(self):
        return f"{self.agent} warp#{self.ship_id}/{self.object_id}[{self.protocol()}]"


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
    # Other methods
    ######################################################
    def init_warp(self, skt, agt, tp, dkr, proto_hnd):
        self.init(skt, agt, tp)
        self.docker = dkr
        if self.docker.timeout_sec >= 0:
            self.socket_timeout_sec = self.docker.timeout_sec
        else:
            self.socket_timeout_sec = bs.BayServer.harbor.socket_timeout_sec
        self.set_protocol_handler(proto_hnd)

    def warp_handler(self):
        return self.protocol_handler

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
        w_hnd.post_warp_headers(tur)

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
        self.docker.keep_ship(self)

    def notify_service_unavailable(self, msg):
        self.notify_error_to_owner_tour(HttpStatus.SERVICE_UNAVAILABLE, msg)

    def get_tour(self, warp_id, must=True):
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
                    tur.res.end_content(Tour.TOUR_ID_NOCHECK)

            self.tour_map.clear()

    def end_ship(self):
        self.docker.return_protocol_handler(self.agent, self.protocol_handler)
        self.docker.return_ship(self)

    def abort(self, check_id):
        self.check_ship_id(check_id)
        self.postman.abort()

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
            self.protocol_handler.command_packer.post(self, cmd, listener)

    def flush(self):
        for cmd_and_lis in self.cmd_buf:
            self.protocol_handler.command_packer.post(self, cmd_and_lis[0], cmd_and_lis[1])
        self.cmd_buf = []



