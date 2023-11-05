import threading

from bayserver_core import bayserver as bs
from bayserver_core.sink import Sink
from bayserver_core.bay_log import BayLog
from bayserver_core.docker.trouble import Trouble
from bayserver_core.watercraft.ship import Ship
from bayserver_core.tour.tour import Tour
from bayserver_core.util.counter import Counter
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.exception_util import ExceptionUtil
from bayserver_core.tour.tour_store import TourStore

class InboundShip(Ship):
    err_counter = Counter()

    MAX_TOURS = 128

    def __init__(self):
        Ship.__init__(self)
        self.port_docker = None
        self.tour_store = None
        self.need_end = None
        self.socket_timeout_sec = None
        self.active_tours = []
        self.lock = threading.RLock()

    def __str__(self):
        return f"{self.agent} ship#{self.ship_id}/{self.object_id}[{self.protocol()}]"

    def init_inbound(self, skt, agt, postman, port, proto_hnd):
        self.init(skt, agt, postman)
        self.port_docker = port
        self.socket_timeout_sec = self.port_docker.timeout_sec if self.port_docker.timeout_sec >= 0 else bs.BayServer.harbor.socket_timeout_sec
        self.tour_store = TourStore.get_store(agt.agent_id)
        self.set_protocol_handler(proto_hnd)

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        super().reset()

        with self.lock:

            if len(self.active_tours) > 0:
                raise Sink(f"{self} There are some running tours")
            self.active_tours.clear()

        self.need_end = False


    ######################################################
    # Other methods
    ######################################################

    def get_tour(self, tur_key, force=False, rent=True):

        store_key = InboundShip.uniq_key(self.ship_id, tur_key)

        with self.lock:
            tur = self.tour_store.get(store_key)

            if tur is None and rent:
                tur = self.tour_store.rent(store_key, force)
                if tur is None:
                    return None

                tur.init(tur_key, self)
                self.active_tours.append(tur)

        return tur

    def get_error_tour(self):
        tur_key = InboundShip.err_counter.next()
        store_key = InboundShip.uniq_key(self.ship_id, -tur_key)
        tur = self.tour_store.rent(store_key, True)
        self.active_tours.append(tur)
        tur.init(-tur_key, self)
        return tur

    def send_headers(self, check_id, tur):
        self.check_ship_id(check_id)

        if tur.is_zombie() or tur.is_aborted():
            # Don't send peer any data
            return


        handled = False
        if not tur.error_handling and tur.res.headers.status >= 400:
            trouble = bs.BayServer.harbor.trouble
            if trouble is not None:
                cmd = trouble.find(tur.res.headers.status)
                if cmd is not None:
                    err_tour = self.get_error_tour()
                    err_tour.req.uri = cmd.target
                    tur.req.headers.copy_to(err_tour.req.headers)
                    tur.res.headers.copy_to(err_tour.res.headers)
                    err_tour.req.remote_port = tur.req.remote_port
                    err_tour.req.remote_address = tur.req.remote_address
                    err_tour.req.server_address = tur.req.server_address
                    err_tour.req.server_port = tur.req.server_port
                    err_tour.req.server_name = tur.req.server_name
                    tur.change_state(Tour.TOUR_ID_NOCHECK, Tour.TourState.ZOMBIE)

                    if cmd.method == Trouble.GUIDE:
                        err_tour.go()
                    elif cmd.method == Trouble.TEXT:
                        self.protocol_handler.send_res_headers(err_tour)
                        data = cmd.target
                        self.send_res_content(check_id, err_tour, data, 0, data.length)
                        self.send_end_tour(check_id, err_tour)
                    elif cmd.method == Trouble.REROUTE:
                        self.send_redirect(check_id, err_tour, HttpStatus.MOVED_TEMPORARILY, cmd.target)
                        self.send_end_tour(check_id, err_tour)

                    handled = True


        if not handled:
            for nv in self.port_docker.additional_headers:
                tur.res.headers.add(nv[0], nv[1])
            self.protocol_handler.send_res_headers(tur)


    def send_redirect(self, check_id, tur, status, location):
        self.check_ship_id(check_id)

        hdr = tur.res.headers
        hdr.status = status
        hdr.set(Headers.LOCATION, location)

        body = "<H2>Document Moved.</H2><BR>" + "<A HREF=\"" + location + "\">" + location + "</A>"

        self.send_error_content(check_id, tur, StringUtil.to_bytes(body))


    def send_res_content(self, chk_ship_id, tur, bytes, ofs, length, callback):
        BayLog.debug("%s send_res_content bytes: %d", self, length)

        self.check_ship_id(chk_ship_id)

        max_len = self.protocol_handler.max_res_packet_data_size()
        while length > max_len:
            self.protocol_handler.send_res_content(tur, bytes, ofs, max_len, None)
            ofs = ofs + max_len
            length = length - max_len
        if length > 0:
            self.protocol_handler.send_res_content(tur, bytes, ofs, length, callback)


    def send_end_tour(self, chk_ship_id, tur, callback):
        with self.lock:
            self.check_ship_id(chk_ship_id)
            BayLog.debug("%s sendEndTour: %s state=%s", self, tur, tur.state)

            if not tur.is_valid():
              raise Sink("Tour is not valid")

            keep_alive = False
            if tur.req.headers.get_connection() == Headers.CONNECTION_KEEP_ALIVE:
                keep_alive = True
                if keep_alive:
                    res_conn = tur.res.headers.get_connection()
                    keep_alive = (res_conn == Headers.CONNECTION_KEEP_ALIVE) or \
                                (res_conn == Headers.CONNECTION_UNKOWN)

                if keep_alive:
                    if tur.res.headers.content_length() < 0:
                        keep_alive = False

            self.protocol_handler.send_end_tour(tur, keep_alive, callback)



    def send_error(self, chk_id, tour, status, message, e):
        self.check_ship_id(chk_id)

        BayLog.info("%s send error: status=%d, message=%s ex=%s", self, status, message, ExceptionUtil.message(e) if e else "");

        if e is not None:
            BayLog.debug_e(e)

        # Create body
        desc = HttpStatus.description(status)

        # print status
        body = ""
        body +=  "<h1>"
        body += str(status)
        body += " "
        body += desc
        body += "</h1>\r\n"

        tour.res.headers.status = status
        self.send_error_content(chk_id, tour, StringUtil.to_bytes(body))

    def send_error_content(self, chk_id, tour, content):

        # Get charset
        charset = tour.res.charset

        # Set content type
        if StringUtil.is_set(charset):
            tour.res.headers.set_content_type("text/html charset=" + charset)
        else:
            tour.res.headers.set_content_type("text/html")

        if StringUtil.is_set(content):
            tour.res.headers.set_content_length(len(content))

        self.send_headers(chk_id, tour)

        if StringUtil.is_set(content):
            self.send_res_content(chk_id, tour, content, 0, len(content), None)


    def end_ship(self):
        BayLog.debug("%s endShip", self)
        self.port_docker.return_protocol_handler(self.agent, self.protocol_handler)
        self.port_docker.return_ship(self)

    def abort_tours(self):
        return_list = []

        # Abort tours
        for tur in self.active_tours:
            if tur.is_valid():
                BayLog.debug("%s is valid, abort it: stat=%s", tur, tur.state)
                if tur.req.abort():
                    return_list.append(tur)

        for tur in return_list:
            self.return_tour(tur)


    @classmethod
    def uniq_key(cls, sip_id, tur_key):
        return sip_id << 32 | (tur_key & 0xffffffff)


    def return_tour(self, tur):
        BayLog.debug("%s Return tour %s", self, tur)

        with self.lock:
            self.tour_store.Return(InboundShip.uniq_key(self.ship_id, tur.req.key))
            if not tur in self.active_tours:
                raise Sink("Tour is not in acive list: %s", tur)

            self.active_tours.remove(tur)

            if self.need_end and len(self.active_tours) == 0:
                self.end_ship()
