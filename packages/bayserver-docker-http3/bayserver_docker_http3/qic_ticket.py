import time
from typing import Any

from aioquic.h3.connection import H3Connection
from aioquic.h3.events import H3Event, HeadersReceived, DataReceived
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import StreamDataReceived, ConnectionIdIssued, HandshakeCompleted, StopSendingReceived

from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.common.inbound_ship import InboundShip
from bayserver_core.http_exception import HttpException
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.ship.ship import Ship
from bayserver_core.sink import Sink
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.tour.tour import Tour
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.exception_util import ExceptionUtil
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_util import HttpUtil
from bayserver_docker_http3.h3_protocol_handler import H3ProtocolHandler
from bayserver_docker_http3.qic_packet import QicPacket
from bayserver_docker_http3.qic_protocol_handler import QicProtocolHandler


class QicTicket:

    PROTOCOL = "HTTP/3"

    qic_protocol_handler: QicProtocolHandler
    con: QuicConnection
    sender: str
    config: QuicConfiguration
    last_accessed: int
    h3_ship: InboundShip
    hcon: H3Connection
    stop_sending: bool

    def __init__(self, ph: QicProtocolHandler, con: QuicConnection, adr: str, cfg: QuicConfiguration) -> None:
        super().__init__()
        self.qic_protocol_handler = ph
        self.con = con
        self.sender = adr
        self.config = cfg
        self.hcon = None
        self.last_accessed = 0
        self.stop_sending = False

    def __str__(self):
        return f"QicTicket[{self.con.host_cid}]"


    ##################################################
    # Implements TourHandler
    ##################################################

    def send_res_headers(self, tur: Tour) -> None:
        BayLog.debug("%s stm#%d sendResHeader", tur, tur.req.key)

        h3_hdrs = []
        h3_hdrs.append((b":status", str(tur.res.headers.status).encode()))

        for name in tur.res.headers.names():
            if name != "connection":
                for value in tur.res.headers.values(name):
                    h3_hdrs.append((name.encode(), value.encode()))

        if BayServer.harbor.trace_header():
            for hdr in h3_hdrs:
                BayLog.info("%s header %s: %s", tur, hdr[0], hdr[1])

        stm_id = tur.req.key
        try:
            self.hcon.send_headers(stream_id = stm_id, headers = h3_hdrs)
        except Exception as e:
            BayLog.error_e(e, "%s Error on sending headers: %s", tur, ExceptionUtil.message(e))
            raise IOError("Error on sending headers: %s", ExceptionUtil.message(e))

        self.access()

    def send_res_content(self, tur: Tour, buf: bytearray, ofs: int, length: int, lis: DataConsumeListener) -> None:

        stm_id = tur.req.key
        BayLog.debug("%s stm#%d sendResContent len=%d posted=%d/%d",
                     tur, stm_id, length, tur.res.bytes_posted, tur.res.headers.content_length())

        try:
            self.hcon.send_data(stream_id=stm_id, data=bytes(buf[ofs:ofs+length]), end_stream=False)
            self.post_packets()

        except Exception as e:
            BayLog.error_e(e, "%s Error on sending data: %s", tur, ExceptionUtil.message(e))
            raise IOError("Error on sending data: %s", ExceptionUtil.message(e))

        finally:
            if lis:
                lis()

        self.access()

    def send_end_tour(self, tur: Tour, keep_alive: bool, lis: DataConsumeListener) -> None:

        stm_id = tur.req.key
        BayLog.debug("%s stm#%d sendEndTour", tur, stm_id)

        try:
            self.hcon.send_data(stream_id=stm_id, data=b"", end_stream=True)
            self.post_packets()
        except Exception as e:
            # There are some clients that close stream before end_stream received
            BayLog.error_e(e, "%s stm#%d Error on making packet to send (Ignore): %s", self, stm_id, e)
        finally:
            if lis:
                lis()

        self.access()


    def on_protocol_error(self, e: ProtocolException) -> bool:
        raise Sink()


    def notify_read(self, buf: bytes, adr: str) -> None:
        try:
            self.con.receive_datagram(buf, adr, time.time())
        except AssertionError as e:
            BayLog.fatal_e(e, "%s Error on analyzing received packet: %s", self, e)
            raise e
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
                self.on_stream_data_received(ev, adr)
            elif isinstance(ev, events.StreamReset):
                self.on_stream_reset(ev)
            elif isinstance(ev, events.StopSendingReceived):
                self.on_stop_sending_received(ev)
            elif isinstance(ev, events.ConnectionIdIssued):
                self.on_connection_id_issued(ev)
            elif isinstance(ev, events.ConnectionIdRetired):
                pass
            elif isinstance(ev, events.ConnectionTerminated):
                pass
            elif isinstance(ev, events.HandshakeCompleted):
                self.on_handshake_completed(ev)
            elif isinstance(ev, events.PingAcknowledged):
                pass

        self.access()

    ##################################################
    # Quic event handling
    ##################################################
    def on_protocol_negotiated(self, qev):
        self.hcon = H3Connection(self.con, enable_webtransport=True)
        self.h3_ship = InboundShip()
        ph = H3ProtocolHandler(self)
        self.h3_ship.init_inbound(None, self.qic_protocol_handler.ship.agent_id, None, self.qic_protocol_handler.port_docker(), ph)


    def on_stream_data_received(self, qev: StreamDataReceived, adr: Any):
        BayLog.debug("%s stm#%d stream data received: len=%d", self, qev.stream_id, len(qev.data))
        if qev.data == b"quack":
            self.con.send_datagram_frame(b"quack-ack")

        if self.hcon:
            for hev in self.hcon.handle_event(qev):
                self.on_http_event_received(hev, adr)

    def on_stream_reset(self, qev):
        BayLog.debug("%s stm#%d reset: code=%d", self, qev.stream_id, qev.error_code)

        tur = self.h3_ship.get_tour(qev.stream_id, rent=False)
        if tur:
            tur.req.abort()

    def on_stop_sending_received(self, qev: StopSendingReceived):
        BayLog.debug("%s stm#%d stop sending errcode=%d", self, qev.stream_id, qev.error_code)
        self.stop_sending = True

    def on_connection_id_issued(self, qev: ConnectionIdIssued):
        BayLog.debug("%s connection id issued: %s", self, qev.connection_id.hex())

    def on_handshake_completed(self, qev: HandshakeCompleted):
        BayLog.debug("%s handshake completed: %s", self, qev.alpn_protocol)



    ##################################################
    # Http event handling
    ##################################################

    def on_http_event_received(self, hev: H3Event, adr: Any):
        if isinstance(hev, HeadersReceived):
            self.handle_headers(hev)
        elif isinstance(hev, DataReceived):
            self.handle_data(hev)

    def handle_headers(self, hev: HeadersReceived):
        BayLog.debug("%s stm#%d onHeaders", self, hev.stream_id)

        tur = self.h3_ship.get_tour(hev.stream_id)
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
            sid = self.h3_ship.ship_id
            def callback(length, resume):
                self.h3_ship.check_ship_id(sid)
                if resume:
                    self.h3_ship.resume_read(Ship.SHIP_ID_NOCHECK)

            tur.req.set_limit(req_cont_len)

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
                tur.req.set_content_handler(ReqContentHandler.dev_null)
                return

    def handle_data(self, hev: DataReceived):
        BayLog.debug("%s stm#%d onData: len=%d end=%s", self, hev.stream_id, len(hev.data), hev.stream_ended)

        tur = self.h3_ship.get_tour(hev.stream_id, rent=False)
        if tur is None:
            BayLog.debug("%s stm#%d No tour related (Ignore)", self, hev.stream_id)
            return

        elif tur.req.ended:
            BayLog.debug("%s stm#%d Tour is already ended (Ignore)", self, hev.stream_id)
            return


        sid = self.h3_ship.ship_id
        def callback(length: int, resume: bool):
            if resume:
                self.h3_ship.resume_read(sid)

        tur.req.post_req_content(Tour.TOUR_ID_NOCHECK, hev.data, 0, len(hev.data), callback)

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



    def is_timed_out(self):
        duration_sec = int(time.time()) - self.last_accessed
        BayLog.info("%s Check H3 timeout duration=%d", self, duration_sec)
        if duration_sec > BayServer.harbor.socket_timeout_sec():
            BayLog.info("%s H3 Connection is timed out", self)
            try:
                self.con.close()
            except BaseException as e:
                BayLog.error_e(e, "%s Close Error", self)
            return True
        else:
            return False

    def access(self):
        self.last_accessed = int(time.time())

    def post_packets(self):
        posted = False
        if not self.stop_sending:
            for buf, adr in self.con.datagrams_to_send(now=time.time()):
                BayLog.debug("%s POST packet: len=%d", self, len(buf))
                pkt = QicPacket()
                # For performance reasons, we update the attribute 'buf' directly.
                pkt.buf = bytearray(buf)
                pkt.bufLen = len(pkt.buf)
                self.qic_protocol_handler.packet_packer.post(self.qic_protocol_handler.ship, adr, pkt, None)
                posted = True
        return posted

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



