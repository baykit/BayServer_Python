import traceback

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.bayserver import BayServer
from bayserver_core.common.inbound_handler import InboundHandler
from bayserver_core.http_exception import HttpException
from bayserver_core.sink import Sink
from bayserver_core.symbol import Symbol
from bayserver_core.tour.tour import Tour
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.http_util import HttpUtil

from bayserver_docker_http3.h3_error_code import H3ErrorCode
from bayserver_docker_http3.qic_handler import QicHandler
from bayserver_docker_http3.qic_packet import QicPacket


class QicInboundHandler(InboundHandler, QicHandler):
    """Per-connection H3 inbound handler. Owns the BayServer-side per-stream
    bookkeeping (Tour mapping, request body forwarding) and translates H3
    events parsed by QicProtocolHandler into Tour state changes."""

    H3_MESSAGE_ERROR = 0x10e

    def __init__(self):
        super().__init__()
        self.protocol_handler = None

    def init(self, protocol_handler):
        self.protocol_handler = protocol_handler

    def reset(self):
        pass

    ######################################################
    # Implements InboundHandler
    ######################################################

    def send_res_headers(self, tur):
        stm_id = tur.req.key
        BayLog.debug("%s stm#%d send_res_headers", tur, stm_id)

        h3_headers = []
        h3_headers.append((b":status", str(tur.res.headers.status).encode("ascii")))
        for name in tur.res.headers.names():
            for value in tur.res.headers.values(name):
                h3_headers.append((name.encode("ascii", errors="replace"),
                                   value.encode("ascii", errors="replace")))

        if BayServer.harbor.trace_header():
            for hn, hv in h3_headers:
                BayLog.info("%s header %s: %s", tur, hn, hv)

        from croute.error import CrouteError
        try:
            self.protocol_handler.h3con.send_response(stm_id, h3_headers, False)
            self.protocol_handler.post_packets()
        except CrouteError as e:
            if getattr(e, "code", None) == CrouteError.H3_ERR_STREAM_BLOCKED:
                BayLog.warn("%s stm#%d sending header is blocked", tur, stm_id)
                from bayserver_docker_http3.qic_protocol_handler import _PartialResponse
                self.protocol_handler.add_partial_response(
                    stm_id, _PartialResponse(headers=h3_headers))
            elif getattr(e, "code", None) == CrouteError.H3_ERR_TRANSPORT_ERROR:
                qerr = self.protocol_handler.peer_or_local_error_code()
                raise IOError(f"h3: send header failed (transport): qerr={qerr}")
            else:
                raise IOError(f"h3: send header failed: {H3ErrorCode.get_message(e.code)}({e.code})")

    def send_res_content(self, tur, data, ofs, length, listener):
        stm_id = tur.req.key
        BayLog.debug("%s stm#%d send_res_content len=%d posted=%d/%d", tur, stm_id, length,
                     tur.res.bytes_posted, tur.res.headers.content_length())

        if ofs > 0 or length < len(data):
            body = bytes(data[ofs:ofs + length])
        else:
            body = bytes(data)

        from bayserver_docker_http3.qic_protocol_handler import _PartialResponse
        from croute.error import CrouteError

        part = None
        if stm_id in self.protocol_handler.partial_responses:
            BayLog.trace("%s stm#%d waiting. enqueue len=%d", tur, stm_id, length)
            part = _PartialResponse(body=body, listener=listener)
        else:
            try:
                n = self.protocol_handler.h3con.send_body(stm_id, body, False)
            except CrouteError as e:
                if getattr(e, "code", None) == CrouteError.H3_ERR_FRAME_UNEXPECTED:
                    part = _PartialResponse(body=body, listener=listener)
                elif getattr(e, "code", None) == CrouteError.H3_ERR_TRANSPORT_ERROR:
                    qerr = self.protocol_handler.peer_or_local_error_code()
                    raise IOError(f"h3: send body failed (transport): qerr={qerr}")
                else:
                    raise IOError(f"h3: send body failed: {H3ErrorCode.get_message(e.code)}({e.code})")
            else:
                if n == 0:
                    part = _PartialResponse(body=body, listener=listener)
                elif n < length:
                    part = _PartialResponse(body=body, ofs=n, listener=listener)

        if part is not None:
            self.protocol_handler.add_partial_response(stm_id, part)
        elif listener is not None:
            try:
                listener(True, False)
            except Exception as e:
                BayLog.error_e(e, traceback.format_stack())

        self.protocol_handler.post_packets()
        return True

    def send_end_tour(self, tur, listener):
        stm_id = tur.req.key
        BayLog.debug("%s stm#%d send_end_tour", tur, stm_id)

        from bayserver_docker_http3.qic_protocol_handler import _PartialResponse
        from croute.error import CrouteError

        retry = False
        if stm_id in self.protocol_handler.partial_responses:
            BayLog.debug("stm#%d put fin into queue", stm_id)
            retry = True
        else:
            try:
                self.protocol_handler.h3con.send_body(stm_id, b"", True)
            except CrouteError as e:
                code = getattr(e, "code", None)
                if code == CrouteError.H3_ERR_FRAME_UNEXPECTED:
                    BayLog.warn("stm#%d send end frame unexpected", stm_id)
                    retry = True
                elif code == CrouteError.H3_ERR_TRANSPORT_ERROR:
                    qerr = self.protocol_handler.peer_or_local_error_code()
                    raise IOError(f"h3: send body fin failed (transport): qerr={qerr}")
                else:
                    raise IOError(f"h3: send body fin failed: {H3ErrorCode.get_message(code)}({code})")

        if retry:
            self.protocol_handler.add_partial_response(
                stm_id, _PartialResponse(fin=True, listener=listener))
        elif listener is not None:
            try:
                listener(True, False)
            except Exception as e:
                BayLog.error_e(e, traceback.format_stack())

        self.protocol_handler.post_packets()

    def transfer_content(self, tur, file_rd, ofs, length, listener):
        raise Sink()

    def on_protocol_error(self, err, stk=None):
        BayLog.debug_e(err, stk if stk is not None else traceback.format_stack())
        return False

    ######################################################
    # Implements QicHandler
    ######################################################

    def handle_headers(self, cmd):
        BayLog.debug("%s stm#%d onHeaders", self, cmd.stm_id)

        try:
            tur = self._get_tour(cmd.stm_id)
            if tur is None:
                self._tour_is_unavailable(cmd.stm_id)
                return

            if not self._validate_pseudo_headers(cmd):
                self._close_with_h3_error(QicInboundHandler.H3_MESSAGE_ERROR,
                                          "malformed pseudo-headers")
                return

            for hn, hv in cmd.req_headers:
                name = hn.decode("ascii", errors="replace") if isinstance(hn, (bytes, bytearray)) else hn
                value = hv.decode("ascii", errors="replace") if isinstance(hv, (bytes, bytearray)) else hv
                if BayServer.harbor.trace_header():
                    BayLog.info("%s stm#%d ReqHeader %s=%s", tur, cmd.stm_id, name, value)
                lname = name.lower()
                if lname == ":path":
                    tur.req.uri = value
                elif lname == ":authority":
                    tur.req.headers.add(Headers.HOST, value)
                elif lname == ":scheme":
                    tur.is_secure = value.lower() == "https"
                elif lname == ":method":
                    tur.req.method = value
                elif not name.startswith(":"):
                    tur.req.headers.add(name, value)

            BayLog.debug("%s stm#%d onHeader: method=%s uri=%s",
                         tur, cmd.stm_id, tur.req.method, tur.req.uri)

            req_cont_len = tur.req.headers.content_length()
            if req_cont_len > 0:
                tur.req.set_limit(req_cont_len)

            try:
                self._start_tour(tur)
                if tur.req.headers.content_length() <= 0:
                    self._end_req_content(Tour.TOUR_ID_NOCHECK, tur)
            except HttpException as e:
                BayLog.debug("%s Http error: %s", self, e)
                if req_cont_len <= 0:
                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e, traceback.format_stack())
                else:
                    tur.error = e
                    tur.stack = traceback.format_stack()
        except Exception as e:
            BayLog.error_e(e, traceback.format_stack())

    def handle_data(self, cmd):
        BayLog.debug("%s stm#%d onData", self, cmd.stm_id)

        try:
            tur = self._get_tour(cmd.stm_id)
            if tur is None:
                self._tour_is_unavailable(cmd.stm_id)
                return

            from croute.error import CrouteError
            from croute.binding import ERR_DONE

            buf = bytearray(QicPacket.MAX_DATAGRAM_SIZE)
            # Drain one body chunk per event.
            try:
                n = self.protocol_handler.h3con.recv_body(cmd.stm_id, buf)
            except CrouteError as e:
                BayLog.error("%s stm#%d h3: recv body failed: %s",
                             self, cmd.stm_id, e)
                return

            if n == ERR_DONE or n == 0:
                return

            sid = self.protocol_handler.ship.ship_id

            def consume(length, resume):
                if resume:
                    tur.ship.resume(sid)

            tur.req.post_req_content(Tour.TOUR_ID_NOCHECK, bytes(buf), 0, n, consume)

            if tur.req.bytes_posted >= tur.req.headers.content_length():
                if tur.error is not None:
                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, tur.error, tur.stack)
                else:
                    try:
                        self._end_req_content(tur.id(), tur)
                    except HttpException as e:
                        tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e, traceback.format_stack())
        except Exception as e:
            BayLog.error_e(e, traceback.format_stack())

    def handle_finished(self, cmd):
        BayLog.debug("%s stm#%d onFinished", self, cmd.stm_id)

    ######################################################
    # Private
    ######################################################

    def _get_tour(self, stm_id):
        return self.protocol_handler.ship.get_tour(int(stm_id))

    def _tour_is_unavailable(self, stm_id):
        BayLog.error(BayMessage.get(Symbol.INT_NO_MORE_TOURS))
        tur = self.protocol_handler.ship.get_tour(int(stm_id), True)
        tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.SERVICE_UNAVAILABLE,
                           "No available tours")

    def _end_req_content(self, check_id, tur):
        from croute.binding import SHUTDOWN_READ
        BayLog.debug("%s endReqContent", tur)
        try:
            self.protocol_handler.con.stream_shutdown(tur.req.key, SHUTDOWN_READ, 0)
        except Exception as e:
            BayLog.debug("%s stream_shutdown failed: %s", tur, e)
        tur.req.end_content(check_id)

    def _start_tour(self, tur):
        HttpUtil.parse_host_port(tur, 443)
        HttpUtil.parse_authorization(tur)
        tur.req.protocol = self.protocol_handler.PROTOCOL
        tur.req.remote_port = self.protocol_handler.sender.port
        tur.req.remote_address = self.protocol_handler.sender.ip
        tur.req.remote_host_func = lambda: HttpUtil.resolve_remote_host(tur.req.remote_address)
        tur.req.server_address = self.protocol_handler.sender.ip
        tur.req.server_port = tur.req.req_port
        tur.req.server_name = tur.req.req_host
        tur.is_secure = True
        tur.go()

    def _validate_pseudo_headers(self, cmd):
        seen_pseudo = set()
        saw_regular = False
        method = scheme = path = authority = None
        for hn, hv in cmd.req_headers:
            name = hn.decode("ascii", errors="replace") if isinstance(hn, (bytes, bytearray)) else hn
            value = hv.decode("ascii", errors="replace") if isinstance(hv, (bytes, bytearray)) else hv
            if not name:
                BayLog.debug("%s stm#%d empty header name", self, cmd.stm_id)
                return False
            if name[0] == ":":
                if saw_regular:
                    BayLog.debug("%s stm#%d pseudo-header %s after regular", self, cmd.stm_id, name)
                    return False
                if name in seen_pseudo:
                    BayLog.debug("%s stm#%d duplicated pseudo-header %s", self, cmd.stm_id, name)
                    return False
                seen_pseudo.add(name)
                if name == ":method":
                    method = value
                elif name == ":scheme":
                    scheme = value
                elif name == ":path":
                    path = value
                elif name == ":authority":
                    authority = value
                else:
                    BayLog.debug("%s stm#%d prohibited pseudo-header %s", self, cmd.stm_id, name)
                    return False
            else:
                saw_regular = True
        if method is None:
            BayLog.debug("%s stm#%d missing :method", self, cmd.stm_id)
            return False
        if method.upper() != "CONNECT":
            if scheme is None:
                BayLog.debug("%s stm#%d missing :scheme", self, cmd.stm_id)
                return False
            if not path:
                BayLog.debug("%s stm#%d missing :path", self, cmd.stm_id)
                return False
            if authority is None:
                has_host = False
                for hn, hv in cmd.req_headers:
                    n = hn.decode("ascii", errors="replace") if isinstance(hn, (bytes, bytearray)) else hn
                    if n.lower() == "host":
                        has_host = True
                        break
                if not has_host:
                    BayLog.debug("%s stm#%d missing :authority and Host", self, cmd.stm_id)
                    return False
        return True

    def _close_with_h3_error(self, error_code, reason):
        from croute.error import CrouteError
        BayLog.debug("%s closing H3 connection: code=0x%x reason=%s",
                     self, error_code, reason)
        try:
            self.protocol_handler.con.close_connection(
                True, error_code, reason.encode("ascii", errors="replace"))
        except CrouteError as e:
            BayLog.debug("%s close_connection failed: %s", self, e)
        try:
            self.protocol_handler.post_packets()
        except Exception as e:
            BayLog.debug("%s postPackets after close failed: %s", self, e)
