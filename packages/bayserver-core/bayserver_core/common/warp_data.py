from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.bay_log import BayLog
from bayserver_core.common import warp_ship as ws
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.tour.tour import Tour
from bayserver_core.util.headers import Headers
from bayserver_core.util.data_consume_listener import DataConsumeListener

class WarpData(ReqContentHandler):

    warp_ship: "ws.WarpShip"
    warp_ship_id: int
    warp_id: int
    req_headers: Headers
    res_headers: Headers
    started: bool
    ended: bool

    def __init__(self, warp_ship: "ws.WarpShip", warp_id: int):
        self.warp_ship = warp_ship
        self.warp_ship_id = warp_ship.id()
        self.warp_id = warp_id
        self.req_headers = Headers()
        self.res_headers = Headers()
        self.started = False
        self.ended = False


    def __str__(self):
        return f"{self.warp_ship} wtur#{self.warp_id}"


    def on_read_req_content(self, tur: Tour, buf: bytearray, start: int, length: int, lis: DataConsumeListener):
        BayLog.debug("%s onReadReqContent tur=%s len=%d", self.warp_ship, tur, length)
        self.warp_ship.check_ship_id(self.warp_ship_id)
        max_len = self.warp_ship.protocol_handler.max_req_packet_data_size()
        pos = 0
        while pos < length:
            post_len = length - pos
            if post_len > max_len:
                post_len = max_len

            tur_id = tur.id()
            def callback():
                tur.req.consumed(tur_id, length, lis)

            if not self.started:
                # The buffer will become corrupted due to reuse.
                if isinstance(buf, bytes):
                    buf = bytes(buf)
                else:
                    buf = buf.copy()

            self.warp_ship.warp_handler().send_req_contents(tur, buf, start + pos, post_len, callback)
            pos += max_len

    def on_end_req_content(self, tur: Tour):
        BayLog.debug("%s endReqContent tur=%s", self.warp_ship, tur)
        self.warp_ship.check_ship_id(self.warp_ship_id)

        def callback():
            agt = GrandAgent.get(self.warp_ship.agent_id)
            agt.net_multiplexer.req_read(self.warp_ship.rudder)

        self.warp_ship.warp_handler().send_end_req(tur, False, callback)

    def on_abort_req(self, tur):
        BayLog.debug("%s onAbortReq tur=%s", self.warp_ship, tur)
        self.warp_ship.check_ship_id(self.warp_ship_id)
        self.warp_ship.abort(self.warp_ship_id)
        return False

    def start(self):
        if not self.started:
            BayLog.debug("%s Start Warp tour", self)
            self.warp_ship.flush()
            self.started = True


    @classmethod
    def get(cls, tur):
        return tur.req.content_handler
