import time
import socket
from aioquic.quic import events
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.http_exception import HttpException
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.docker.base.inbound_handler import InboundHandler
from bayserver_core.tour.tour import Tour
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.watercraft.ship import Ship
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_util import HttpUtil
from bayserver_core.util.exception_util import ExceptionUtil

from bayserver_docker_http3.qic_packet import QicPacket


class QicProtocolHandler(ProtocolHandler, InboundHandler):

    MAX_H3_PACKET_SIZE = 1024
    PROTOCOL = "HTTP/3"

    def __init__(self, con, adr, cfg, postman):
        super().__init__()
        self.con = con
        self.sender = adr
        self.config = cfg
        self.postman = postman
        self.hcon = None
        self.last_accessed = None

    def __str__(self):
        return f"{self.ship}"


    ######################################################
    # Implements ProtocolHandler
    ######################################################

    def protocol(self):
        return "h3"

    def max_req_packet_data_size(self):
        return QicProtocolHandler.MAX_H3_PACKET_SIZE

    def max_res_packet_data_size(self):
        #return QicProtocolHandler.MAX_H3_PACKET_SIZE
        return 16000


    def bytes_received(self, buf):

        BayLog.trace("%s Bytes Received: len=%d", self, len(buf))

        try:
            self.con.receive_datagram(buf, self.sender, time.time())
        except Exception as e:
            BayLog.error_e(e, "%s Error on analyzing received packet: %s", self, e)
            raise ProtocolException(f"receive packet failed: {e}")

        while True:
            ev = self.con.next_event()
            if ev is None:
                break

            BayLog.debug("%s event: %s", self, type(ev).__name__)
            if isinstance(ev, events.ProtocolNegotiated):
                self.on_protocol_negotiated(ev)
            elif isinstance(ev, events.StreamDataReceived):
                self.on_stream_data_received(ev)
            elif isinstance(ev, events.StreamReset):
                self.on_stream_reset(ev)
            elif isinstance(ev, events.ConnectionIdIssued):
                pass
            elif isinstance(ev, events.ConnectionIdRetired):
                pass
            elif isinstance(ev, events.ConnectionTerminated):
                pass
            elif isinstance(ev, events.HandshakeCompleted):
                pass
            elif isinstance(ev, events.PingAcknowledged):
                pass
            #self.quic_event_received(event)

        self.access()
        return NextSocketAction.CONTINUE

    ######################################################
    # Implements InboundHandler
    ######################################################

    def send_req_protocol_error(self, protocol_ex):
        return False

    def send_res_headers(self, tur):
        BayLog.debug("%s stm#%d sendResHeader", tur, tur.req.key)

        h3_hdrs = []
        h3_hdrs.append((b":status", str(tur.res.headers.status).encode()))

        for name in tur.res.headers.names():
            for value in tur.res.headers.values(name):
                h3_hdrs.append((name.encode(), value.encode()))

        if BayServer.harbor.trace_header:
            for hdr in h3_hdrs:
                BayLog.info("%s header %s: %s", tur, hdr[0], hdr[1])

        stm_id = tur.req.key
        try:
            self.hcon.send_headers(stream_id = stm_id, headers = h3_hdrs)
        except Exception as e:
            BayLog.error_e(e, "%s Error on sending headers: %s", tur, ExceptionUtil.message(e))
            raise IOError("Error on sending headers: %s", ExceptionUtil.message(e))

        self.access()

    def send_res_content(self, tur, data, ofs, len, callback):

        stm_id = tur.req.key
        BayLog.debug("%s stm#%d sendResContent len=%d posted=%d/%d",
                     tur, stm_id, len, tur.res.bytes_posted, tur.res.headers.content_length())

        try:
            self.hcon.send_data(stream_id=stm_id, data=bytes(data[ofs:ofs+len]), end_stream=False)
            self.post_packets()

        except Exception as e:
            BayLog.error_e(e, "%s Error on sending data: %s", tur, ExceptionUtil.message(e))
            raise IOError("Error on sending data: %s", ExceptionUtil.message(e))

        finally:
            if callback:
                callback()

        self.access()

    def send_end_tour(self, tur, keep_alive, callback):

        stm_id = tur.req.key
        BayLog.debug("%s stm#%d sendEndTour", tur, stm_id)

        try:
            self.hcon.send_data(stream_id=stm_id, data=b"", end_stream=True)
        except Exception as e:
            # There are some clients that close stream before end_stream received
            BayLog.error_e(e, "%s stm#%d Error on making packet to send (Ignore): %s", self, stm_id, e)

        self.post_packets()

        if callback:
            callback()

        self.access()

    ##################################################
    # Quic event handling
    ##################################################
    def on_protocol_negotiated(self, qev):
        self.hcon = H3Connection(self.con, enable_webtransport=True)

    def on_stream_data_received(self, qev):
        BayLog.trace("%s stm#%d stream data received: len=%d", self, qev.stream_id, len(qev.data))
        if qev.data == b"quack":
            self.con.send_datagram_frame(b"quack-ack")

        if self.hcon:
            for hev in self.hcon.handle_event(qev):
                self.on_http_event_received(hev)

    def on_stream_reset(self, qev):
        BayLog.debug("%s stm#%d reset: code=%d", self, qev.stream_id, qev.error_code)

        tur = self.get_tour(qev.stream_id, rent=False)
        if tur:
            tur.req.abort()

    ##################################################
    # Http event handling
    ##################################################

    def on_http_event_received(self, hev):
        if isinstance(hev, HeadersReceived):
            self.on_headers(hev)
        elif isinstance(hev, DataReceived):
            self.on_data(hev)

    def on_headers(self, hev):
        BayLog.debug("%s stm#%d onHeaders", self, hev.stream_id)

        tur = self.get_tour(hev.stream_id)
        if tur is None:
            self.tour_is_unavailable(hev.stream_id)
            return

        for name, value in hev.headers:
            value = value.decode()
            if name == b":authority":
                tur.req.headers.add(Headers.HOST, value)
            elif name == b":method":
                tur.req.method = value
            elif name == b":path":
                tur.req.uri = value
            elif name == b":protocol":
                tur.req.protocol = value
            elif name and not name.startswith(b":"):
                tur.req.headers.add(name.decode(), value)



        req_cont_len = tur.req.headers.content_length()
        BayLog.debug("%s stm#%d onHeader: method=%s uri=%s len=%d", tur, hev.stream_id, tur.req.method, tur.req.uri, req_cont_len)

        if req_cont_len > 0:
            sid = self.ship.ship_id
            def callback(length, resume):
                self.ship.check_ship_id(sid)
                if resume:
                    self.ship.resume(Ship.SHIP_ID_NOCHECK)

            tur.req.set_consume_listener(req_cont_len, callback)

        try:
            self.start_tour(tur)
            if tur.req.headers.content_length() <= 0:
                self.end_req_content(tur.id(), tur)
        except HttpException as e:
            BayLog.debug("%s Http error occurred: %s", self, e)

            if req_cont_len <= 0:
                # no post data
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)
                return
            else:
                # Delay send
                tur.error = e
                tur.req.set_content_handler(ReqContentHandler.devNull)
                return

    def on_data(self, hev):
        BayLog.debug("%s stm#%d onData: len=%d end=%s", self, hev.stream_id, len(hev.data), hev.stream_ended)

        tur = self.get_tour(hev.stream_id, rent=False)
        if tur is None:
            BayLog.debug("%s stm#%d No tour related (Ignore)", self, hev.stream_id)
            return

        elif tur.req.ended:
            BayLog.debug("%s stm#%d Tour is already ended (Ignore)", self, hev.stream_id)
            return

        tur.req.post_content(Tour.TOUR_ID_NOCHECK, hev.data, 0, len(hev.data))

        if hev.stream_ended:
            if tur.error is not None:
                # Error has occurred on header completed
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, tur.error)
            else:
                try:
                    self.end_req_content(tur.id(), tur)
                except HttpException as e:
                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)

    ##################################################
    # Other methods
    ##################################################

    def end_req_content(self, chk_id, tur):
        BayLog.debug("%s endReqContent", tur)
        tur.req.end_content(chk_id)

    def post_packets(self):
        posted = False
        for buf, adr in self.con.datagrams_to_send(now=time.time()):
            pkt = QicPacket()
            # For performance reasons, we update the attribute 'buf' directly.
            pkt.buf = buf
            pkt.bufLen = len(pkt.buf)
            self.postman.post(pkt.buf, adr, pkt, None)
            posted = True
        return posted

    def get_tour(self, stm_id, rent=True):
        tur = self.ship.get_tour(stm_id, rent=rent)
        return tur

    def start_tour(self, tur):
        HttpUtil.parse_host_port(tur, 443)
        HttpUtil.parse_authorization(tur)

        tur.req.protocol = self.PROTOCOL
        tur.req.remote_port = self.sender[1]
        tur.req.remote_address = self.sender[0]

        tur.req.remote_host_func = lambda: HttpUtil.resolve_remote_host(tur.req.remote_address)


        tur.req.server_address = self.sender[0]
        tur.req.server_port = tur.req.req_port
        tur.req.server_name = tur.req.req_host
        tur.is_secure = True
        tur.res.buffer_size = 8192

        tur.go()
        self.access()

    def access(self):
        self.last_accessed = int(time.time())

    def is_timed_out(self):
        duration_sec = int(time.time()) - self.last_accessed
        BayLog.info("%s Check H3 timeout duration=%d", self, duration_sec)
        if duration_sec > BayServer.harbor.socket_timeout_sec:
            BayLog.info("%s H3 Connection is timed out", self)
            try:
                self.con.close()
            except BaseException as e:
                BayLog.error_e(e, "%s Close Error", self)
            return True
        else:
            return False
