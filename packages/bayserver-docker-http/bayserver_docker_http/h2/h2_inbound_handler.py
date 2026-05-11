import traceback
from typing import List

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.bayserver import BayServer
from bayserver_core.common.inbound_handler import InboundHandler
from bayserver_core.common.inbound_ship import InboundShip
from bayserver_core.http_exception import HttpException
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.symbol import Symbol
from bayserver_core.tour.tour import Tour
from bayserver_core.tour.tour_store import TourStore
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.http_util import HttpUtil
from bayserver_core.util.simple_buffer import SimpleBuffer
from bayserver_core.util.string_util import StringUtil
from bayserver_docker_http.h2.command.cmd_data import CmdData
from bayserver_docker_http.h2.command.cmd_go_away import CmdGoAway
from bayserver_docker_http.h2.command.cmd_headers import CmdHeaders
from bayserver_docker_http.h2.command.cmd_ping import CmdPing
from bayserver_docker_http.h2.command.cmd_rst_stream import CmdRstStream
from bayserver_docker_http.h2.command.cmd_settings import CmdSettings
from bayserver_docker_http.h2.command.cmd_window_update import CmdWindowUpdate
from bayserver_docker_http.h2.h2_command_unpacker import H2CommandUnPacker
from bayserver_docker_http.h2.h2_error_code import H2ErrorCode
from bayserver_docker_http.h2.h2_flags import H2Flags
from bayserver_docker_http.h2.h2_handler import H2Handler
from bayserver_docker_http.h2.h2_packet import H2Packet
from bayserver_docker_http.h2.h2_packet_unpacker import H2PacketUnPacker
from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_protocol_exception import H2ProtocolException
from bayserver_docker_http.h2.h2_protocol_handler import H2ProtocolHandler
from bayserver_docker_http.h2.h2_settings import H2Settings
from bayserver_docker_http.h2.header_block import HeaderBlock
from bayserver_docker_http.h2.header_block_analyzer import HeaderBlockAnalyzer
from bayserver_docker_http.h2.header_block_builder import HeaderBlockBuilder
from bayserver_docker_http.h2.header_table import HeaderTable


class H2InboundHandler(H2Handler, InboundHandler):
    class InboundProtocolHandlerFactory:

        def create_protocol_handler(self, pkt_store):
            ib_handler = H2InboundHandler()
            cmd_unpacker = H2CommandUnPacker(ib_handler)
            pkt_unpacker = H2PacketUnPacker(cmd_unpacker, pkt_store, True)
            pkt_packer = PacketPacker()
            cmd_packer = CommandPacker(pkt_packer, pkt_store)

            proto_handler = H2ProtocolHandler(ib_handler, pkt_unpacker, pkt_packer, cmd_unpacker, cmd_packer, True)
            ib_handler.init(proto_handler)
            return proto_handler

    # RFC 7540 § 6.9.1: flow-control window must not exceed 2^31-1.
    MAX_WINDOW = 0x7FFFFFFF
    DEFAULT_INITIAL_WINDOW = 65535

    protocol_handler: H2ProtocolHandler
    header_read: bool
    http_protocol: str

    req_cont_len: int
    req_cont_read: int
    window_size: int
    settings: H2Settings
    analyzer: HeaderBlockAnalyzer
    req_header_tbl: HeaderTable
    res_header_tbl: HeaderTable

    def __init__(self):
        super().__init__()
        self.window_size = BayServer.harbor.tour_buffer_size()
        self.settings = H2Settings()
        self.analyzer = HeaderBlockAnalyzer()
        self.req_cont_len = None
        self.req_cont_read = None
        self.header_read = None
        self.http_protocol = None
        self.req_header_tbl = HeaderTable.create_dynamic_table()
        self.res_header_tbl = HeaderTable.create_dynamic_table()
        # Multi-frame header block buffer (HEADERS without END_HEADERS + CONTINUATION...)
        self.header_buffer = SimpleBuffer()
        self.header_buffer_stream_id = 0
        self._pending_blocks = []
        self._pending_end_stream = False
        # Flow control tracking (RFC 7540 § 6.9.1). Only tracked; outgoing
        # DATA is not yet gated.
        self.conn_send_window = H2InboundHandler.DEFAULT_INITIAL_WINDOW
        self.stream_send_windows = {}

    def init(self, ph: H2ProtocolHandler):
        self.protocol_handler = ph

    def ship(self) -> InboundShip:
        return self.protocol_handler.ship

    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        super().reset()
        self.header_read = False
        self.req_cont_len = 0
        self.req_cont_read = 0
        self.header_buffer.reset()
        self.header_buffer_stream_id = 0
        # Flow control tracking is per-connection; pooled handlers must
        # start each new connection with fresh windows.
        self.conn_send_window = H2InboundHandler.DEFAULT_INITIAL_WINDOW
        self.stream_send_windows = {}
        # Also reset the command unpacker's stream-state machine.
        try:
            self.protocol_handler.command_unpacker.reset()
        except Exception:
            pass

    ######################################################
    # implements InboundHandler
    ######################################################

    def send_res_headers(self, tur):
        cmd = CmdHeaders(tur.req.key)
        bld = HeaderBlockBuilder()
        blk = bld.build_header_block(":status", str(tur.res.headers.status), self.res_header_tbl)
        cmd.header_blocks.append(blk)

        # headers
        if BayServer.harbor.trace_header():
            BayLog.info("%s res status: %d", tur, tur.res.headers.status)

        for name in tur.res.headers.names():
            if StringUtil.eq_ignorecase(name, "connection"):
                BayLog.trace("%s Connection header is discarded", tur)
            else:
                for value in tur.res.headers.values(name):
                    if BayServer.harbor.trace_header():
                        BayLog.info("%s H2 res header: %s=%s", tur, name, value)

                    blk = bld.build_header_block(name, value, self.res_header_tbl)
                    cmd.header_blocks.append(blk)

        cmd.flags.set_end_headers(True)
        cmd.excluded = True
        cmd.flags.set_padded(False)
        self.protocol_handler.post(cmd)

    def send_res_content(self, tur, bytes, ofs, length, callback):
        cmd = CmdData(tur.req.key, None, bytes, ofs, length)
        self.protocol_handler.post(cmd, callback)

    def transfer_content(self, tur, file_rd, ofs, length, lis):
        from bayserver_core.sink import Sink
        # H2 framing requires user-space encoding, so Direct Boarding is unsupported.
        raise Sink()

    def send_end_tour(self, tur, callback):
        cmd = CmdData(tur.req.key, None, [], 0, 0)
        cmd.flags.set_end_stream(True)
        self.protocol_handler.post(cmd, callback)

    def on_protocol_error(self, err: ProtocolException, stk: List[str]) -> None:
        BayLog.error_e(err, stk)

        cmd = CmdGoAway(H2ProtocolHandler.CTL_STREAM_ID)
        cmd.stream_id = 0
        cmd.last_stream_id = 0
        # H2ProtocolException carries a caller-specified error code
        # (FLOW_CONTROL_ERROR, COMPRESSION_ERROR, REFUSED_STREAM, etc.).
        # Bare ProtocolException defaults to PROTOCOL_ERROR per § 5.4.
        if isinstance(err, H2ProtocolException):
            cmd.error_code = err.error_code
        else:
            cmd.error_code = H2ErrorCode.PROTOCOL_ERROR
        cmd.debug_data = b"Thank you!"
        # Defer the close until the GOAWAY has actually been written.
        # Calling post_close synchronously would often close the socket
        # before the GOAWAY reaches the peer (h2spec would see "unexpected
        # EOF" instead of the GOAWAY frame).
        ship_ref = self.protocol_handler.ship

        def _after_goaway():
            try:
                ship_ref.post_close()
            except IOError as e:
                BayLog.error_e(e, traceback.format_stack())

        try:
            self.protocol_handler.post(cmd, _after_goaway)
        except IOError as e:
            BayLog.error_e(e, traceback.format_stack())
        return False

    ######################################################
    # implements H2CommandHandler
    ######################################################

    def handle_preface(self, cmd):
        BayLog.debug("%s h2: handle_preface: proto=%s", self.ship(), cmd.protocol)

        self.http_protocol = cmd.protocol

        sett = CmdSettings(H2ProtocolHandler.CTL_STREAM_ID)
        sett.stream_id = 0
        sett.items.append(CmdSettings.Item(CmdSettings.MAX_CONCURRENT_STREAMS, InboundShip.MAX_TOURS))
        sett.items.append(CmdSettings.Item(CmdSettings.INITIAL_WINDOW_SIZE, self.window_size))
        self.protocol_handler.post(sett)

        sett = CmdSettings(H2ProtocolHandler.CTL_STREAM_ID)
        sett.stream_id = 0
        sett.flags.set_ack(True)

        return NextSocketAction.CONTINUE

    def handle_headers(self, cmd):
        BayLog.debug("%s handle_headers: stm=%d dep=%d weight=%d", self.ship(), cmd.stream_id, cmd.stream_dependency,
                     cmd.weight)

        tur = self.get_tour(cmd.stream_id)
        if tur is None:
            # RFC 7540 § 5.1.2: peer exceeded MAX_CONCURRENT_STREAMS; refuse
            # with RST_STREAM(REFUSED_STREAM). Returning 503 would itself
            # consume a tour slot.
            BayLog.error(BayMessage.get(Symbol.INT_NO_MORE_TOURS))
            rst = CmdRstStream(cmd.stream_id)
            rst.error_code = H2ErrorCode.REFUSED_STREAM
            self.protocol_handler.post(rst)
            return NextSocketAction.CONTINUE

        # Multi-frame header block handling. HPACK encoding may span
        # HEADERS+CONTINUATION boundaries (RFC 7540 § 6.2 / § 6.10), so
        # parsing has to be deferred until END_HEADERS arrives on the
        # last frame; cmd.data / cmd.start / cmd.length is the raw fragment
        # captured by CmdHeaders.unpack.
        end_stream = cmd.flags.end_stream()
        # First HEADERS frame of a new block — remember end_stream from it,
        # which is the authoritative end-of-body signal for the request.
        if self.header_buffer_stream_id == 0:
            self.header_buffer_stream_id = cmd.stream_id
            self._pending_end_stream = end_stream
            self.header_buffer.reset()
        elif cmd.stream_id != self.header_buffer_stream_id:
            raise ProtocolException(
                f"CONTINUATION stream id mismatch: expected {self.header_buffer_stream_id}, got {cmd.stream_id}")

        if cmd.data is not None and cmd.length > 0:
            self.header_buffer.put(cmd.data, cmd.start, cmd.length)

        if cmd.flags.end_headers():
            buf_bytes = bytes(self.header_buffer.buf[:len(self.header_buffer)])
            pend_end = self._pending_end_stream
            self.header_buffer.reset()
            self.header_buffer_stream_id = 0
            self._pending_end_stream = False
            blocks = self._parse_combined_block(buf_bytes)
            return self._on_end_header(tur, blocks, pend_end)
        return NextSocketAction.CONTINUE

    def _parse_combined_block(self, raw_bytes):
        """Re-parse a multi-frame HPACK header-block fragment by synthesizing
        an H2Packet whose data area contains the combined bytes."""
        synth = H2Packet(H2Type.HEADERS)
        # Make the buffer large enough and copy the bytes directly,
        # then advance buf_len so the read accessor's bounds match.
        end = synth.header_len + len(raw_bytes)
        if len(synth.buf) < end:
            synth.buf.extend(bytes(end - len(synth.buf)))
        synth.buf[synth.header_len:end] = raw_bytes
        synth.buf_len = end
        acc = synth.new_h2_data_accessor()
        blocks = []
        seen_non_size_update = False
        while acc.pos < len(raw_bytes):
            blk = HeaderBlock.unpack(acc)
            if blk.op == HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE:
                if seen_non_size_update:
                    raise ProtocolException(
                        "Dynamic table size update must appear at the start of a header block")
            else:
                seen_non_size_update = True
            blocks.append(blk)
        return blocks

    def _on_end_header(self, tur, header_blocks, end_stream):
        # Pseudo-header + header-field validation (RFC 7540 § 8.1.2).
        saw_method = False
        saw_scheme = False
        saw_path = False
        saw_authority = False
        saw_regular_header = False

        try:
            for blk in header_blocks:
                if blk.op == HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE:
                    BayLog.trace("%s header block update table size: %d", tur, blk.size)
                    self.req_header_tbl.set_size(blk.size)
                    continue

                self.analyzer.analyze_header_block(blk, self.req_header_tbl)
                if BayServer.harbor.trace_header():
                    BayLog.info("%s req header: %s=%s :%s",
                                tur, self.analyzer.name, self.analyzer.value, blk)

                if self.analyzer.name is None:
                    continue

                raw_name = self.analyzer.raw_name
                if raw_name is None:
                    raw_name = self.analyzer.name

                # § 8.1.2: header field names must be lowercase.
                if H2InboundHandler._has_upper_case(raw_name):
                    raise ProtocolException(f"Header name must be lowercase: {raw_name}")

                if self.analyzer.pseudo:
                    # § 8.1.2.1: pseudo-headers must precede regular headers.
                    if saw_regular_header:
                        raise ProtocolException(
                            f"Pseudo-header {raw_name} appears after a regular header")

                    if raw_name == HeaderTable.PSEUDO_HEADER_METHOD:
                        if saw_method:
                            raise ProtocolException("Duplicated :method")
                        saw_method = True
                        tur.req.method = self.analyzer.method
                    elif raw_name == HeaderTable.PSEUDO_HEADER_SCHEME:
                        if saw_scheme:
                            raise ProtocolException("Duplicated :scheme")
                        saw_scheme = True
                    elif raw_name == HeaderTable.PSEUDO_HEADER_PATH:
                        if saw_path:
                            raise ProtocolException("Duplicated :path")
                        # § 8.1.2.3: :path must not be empty for http/https.
                        if self.analyzer.path is None or self.analyzer.path == "":
                            raise ProtocolException("Empty :path pseudo-header")
                        saw_path = True
                        tur.req.uri = self.analyzer.path
                    elif raw_name == HeaderTable.PSEUDO_HEADER_AUTHORITY:
                        if saw_authority:
                            raise ProtocolException("Duplicated :authority")
                        saw_authority = True
                        tur.req.headers.add(self.analyzer.name, self.analyzer.value)
                    elif raw_name == HeaderTable.PSEUDO_HEADER_STATUS:
                        raise ProtocolException(":status pseudo-header is invalid in a request")
                    else:
                        raise ProtocolException(f"Unknown pseudo-header: {raw_name}")
                else:
                    saw_regular_header = True
                    # § 8.1.2.2: connection-specific headers are forbidden.
                    lname = self.analyzer.name.lower()
                    if lname in ("connection", "keep-alive", "proxy-connection",
                                 "transfer-encoding", "upgrade"):
                        raise ProtocolException(
                            f"Connection-specific header in HTTP/2: {self.analyzer.name}")
                    if lname == "te" and self.analyzer.value is not None \
                            and self.analyzer.value.lower() != "trailers":
                        raise ProtocolException(
                            f"TE header with value other than 'trailers': {self.analyzer.value}")
                    tur.req.headers.add(self.analyzer.name, self.analyzer.value)
        except (IndexError, ValueError, KeyError) as e:
            # § 7541 § 2.3.3: HPACK decode errors -> COMPRESSION_ERROR.
            raise H2ProtocolException(H2ErrorCode.COMPRESSION_ERROR, f"HPACK decode failed: {e}")

        # § 8.1.2.3: request MUST include :method, :scheme, :path.
        if not saw_method:
            raise ProtocolException("Missing :method pseudo-header")
        if not saw_scheme:
            raise ProtocolException("Missing :scheme pseudo-header")
        if not saw_path:
            raise ProtocolException("Missing :path pseudo-header")

        tur.req.protocol = "HTTP/2.0"
        BayLog.debug("%s H2 read header method=%s protocol=%s uri=%s contlen=%d",
                     self.ship(), tur.req.method, tur.req.protocol, tur.req.uri,
                     tur.req.headers.content_length())

        HttpUtil.check_uri(tur.req.uri)

        # If a body is coming (no END_STREAM on HEADERS) but the peer
        # did not advertise a content-length, set a placeholder so
        # tour.go() puts the tour into READING state instead of
        # RUNNING. END_STREAM on the trailing DATA frame is the
        # authoritative end-of-body signal; mark the placeholder so
        # the content-length consistency check (handle_data) skips it.
        if not end_stream and tur.req.headers.content_length() < 0:
            tur.req.headers.set_content_length(1 << 30)
            tur._h2_placeholder_clen = True
        else:
            tur._h2_placeholder_clen = False

        req_cont_len = tur.req.headers.content_length()
        if req_cont_len > 0:
            tur.req.set_limit(req_cont_len)

        try:
            if tur.req.uri is None:
                raise HttpException(HttpStatus.BAD_REQUEST, "Missing uri")

            self.start_tour(tur)
            if end_stream:
                self.end_req_content(Tour.TOUR_ID_NOCHECK, tur)

        except HttpException as e:
            BayLog.debug("%s Http error occurred: %s", self, e)
            if req_cont_len <= 0:
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e, traceback.format_stack())
                return NextSocketAction.CONTINUE
            else:
                tur.error = e
                tur.stack = traceback.format_stack()
                return NextSocketAction.CONTINUE

        return NextSocketAction.CONTINUE

    def handle_data(self, cmd):
        BayLog.debug("%s handle_data: stm=%d len=%d", self.ship(), cmd.stream_id, cmd.length)

        tur = self.get_tour(cmd.stream_id)
        if tur is None:
            raise RuntimeError(f"Invalid stream id: {cmd.stream_id}")

        # RFC 7540 § 8.1.2.6: if content-length is given, sum of DATA payload
        # lengths MUST match it. Detect at END_STREAM boundary. Skip the
        # check when the peer omitted content-length and we set a placeholder
        # so tour.go() would enter READING state.
        if cmd.flags.end_stream() and not getattr(tur, "_h2_placeholder_clen", False):
            cont_len = tur.req.headers.content_length()
            if cont_len >= 0 and tur.req.bytes_posted + cmd.length != cont_len:
                raise ProtocolException(
                    f"content-length {cont_len} does not match DATA payload "
                    f"{tur.req.bytes_posted + cmd.length}")

        success = True
        if cmd.length > 0:
            tid = tur.tour_id

            def callback(length: int, resume: bool):
                tur.check_tour_id(tid)
                if length > 0:
                    upd = CmdWindowUpdate(cmd.stream_id)
                    upd.window_size_increment = length
                    upd2 = CmdWindowUpdate(0)
                    upd2.window_size_increment = length
                    try:
                        self.protocol_handler.post(upd)
                        self.protocol_handler.post(upd2)
                    except IOError as ex:
                        BayLog.error_e(ex, traceback.format_stack())

                if resume:
                    tur.ship.resume(tur.ship.id)

            success = tur.req.post_req_content(
                Tour.TOUR_ID_NOCHECK,
                cmd.data,
                cmd.start,
                cmd.length,
                callback
            )

        # End the request body either when END_STREAM is signaled or, when
        # content-length is known, when we have received the full payload.
        cont_len = tur.req.headers.content_length()
        if cmd.flags.end_stream() or (cont_len > 0 and tur.req.bytes_posted >= cont_len):
            if tur.error:
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, tur.error, tur.stack)
                return NextSocketAction.CONTINUE
            else:
                # When we used the placeholder content-length (no advertised
                # content-length), align bytes_limit with bytes_posted so the
                # TourReq.end_content length check passes.
                if getattr(tur, "_h2_placeholder_clen", False):
                    tur.req.bytes_limit = tur.req.bytes_posted
                try:
                    self.end_req_content(tur.id(), tur)
                except HttpException as e:
                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e, traceback.format_stack())
                    return NextSocketAction.CONTINUE

        if not success:
            return NextSocketAction.SUSPEND
        else:
            return NextSocketAction.CONTINUE

    def handle_priority(self, cmd):
        if cmd.stream_id == 0:
            raise ProtocolException("Invalid stream id")

        BayLog.debug("%s handlePriority: stmid=%d dep=%d, wgt=%d",
                     self.ship(), cmd.stream_id, cmd.stream_dependency, cmd.weight)

        return NextSocketAction.CONTINUE

    def handle_settings(self, cmd):
        BayLog.debug("%s handleSettings: stmid=%d", self.ship(), cmd.stream_id)

        if cmd.flags.ack():
            return NextSocketAction.CONTINUE

        for item in cmd.items:
            BayLog.debug("%s handle: Setting id=%d, value=%d", self.ship(), item.id, item.value)

            if item.id == CmdSettings.HEADER_TABLE_SIZE:
                self.settings.header_table_size = item.value

            elif item.id == CmdSettings.ENABLE_PUSH:
                # RFC 7540 § 6.5.2: ENABLE_PUSH must be 0 or 1.
                if item.value != 0 and item.value != 1:
                    raise ProtocolException(
                        f"SETTINGS_ENABLE_PUSH must be 0 or 1, got {item.value}")
                self.settings.enable_push = (item.value != 0)

            elif item.id == CmdSettings.MAX_CONCURRENT_STREAMS:
                self.settings.max_concurrent_streams = item.value

            elif item.id == CmdSettings.INITIAL_WINDOW_SIZE:
                # RFC 7540 § 6.5.2: INITIAL_WINDOW_SIZE must not exceed 2^31-1
                # (FLOW_CONTROL_ERROR).
                if item.value < 0 or item.value > H2InboundHandler.MAX_WINDOW:
                    raise H2ProtocolException(
                        H2ErrorCode.FLOW_CONTROL_ERROR,
                        f"SETTINGS_INITIAL_WINDOW_SIZE exceeds 2^31-1: {item.value}")
                self.settings.initial_window_size = item.value

            elif item.id == CmdSettings.MAX_FRAME_SIZE:
                # RFC 7540 § 6.5.2: must be within [2^14, 2^24-1].
                if item.value < H2Packet.DEFAULT_PAYLOAD_MAXLEN or item.value > H2Packet.MAX_PAYLOAD_LEN:
                    raise ProtocolException(
                        f"SETTINGS_MAX_FRAME_SIZE out of range: {item.value}")
                self.settings.max_frame_size = item.value

            elif item.id == CmdSettings.MAX_HEADER_LIST_SIZE:
                self.settings.max_header_list_size = item.value

            else:
                BayLog.debug("Invalid settings id (Ignore): %d", item.id)

        res = CmdSettings(0, H2Flags(H2Flags.FLAGS_ACK))
        self.protocol_handler.post(res)
        return NextSocketAction.CONTINUE

    def handle_window_update(self, cmd):
        # RFC 7540 § 6.9: WINDOW_UPDATE with increment 0 is PROTOCOL_ERROR.
        if cmd.window_size_increment == 0:
            raise ProtocolException("Invalid increment value")

        BayLog.debug("%s handleWindowUpdate: stmid=%d siz=%d",
                     self.ship(), cmd.stream_id, cmd.window_size_increment)

        # RFC 7540 § 6.9.1: adding the increment must not push window above
        # 2^31-1. Overflow at conn level -> FLOW_CONTROL_ERROR (GOAWAY);
        # at stream level -> RST_STREAM.
        inc = cmd.window_size_increment & 0xFFFFFFFF
        if cmd.stream_id == 0:
            self.conn_send_window += inc
            if self.conn_send_window > H2InboundHandler.MAX_WINDOW:
                raise H2ProtocolException(
                    H2ErrorCode.FLOW_CONTROL_ERROR,
                    f"Connection send window overflow: {self.conn_send_window}")
        else:
            win = self.stream_send_windows.get(
                cmd.stream_id, H2InboundHandler.DEFAULT_INITIAL_WINDOW) + inc
            if win > H2InboundHandler.MAX_WINDOW:
                rst = CmdRstStream(cmd.stream_id)
                rst.error_code = H2ErrorCode.FLOW_CONTROL_ERROR
                self.protocol_handler.post(rst)
                self.stream_send_windows.pop(cmd.stream_id, None)
                return NextSocketAction.CONTINUE
            self.stream_send_windows[cmd.stream_id] = win

        return NextSocketAction.CONTINUE

    def handle_go_away(self, cmd):
        BayLog.debug("%s received GoAway: lastStm=%d code=%d desc=%s debug=%s",
                     self.ship(), cmd.last_stream_id, cmd.error_code, H2ErrorCode.msg.get(str(cmd.error_code)),
                     cmd.debug_data)
        return NextSocketAction.CLOSE

    def handle_ping(self, cmd):
        BayLog.debug("%s handle_ping: stm=%d ack=%s", self.ship(), cmd.stream_id, cmd.flags.ack())

        # RFC 7540 § 6.7: PING with ACK is a response to a PING the endpoint
        # sent; we never send PINGs, and MUST NOT respond to PING ACK.
        if cmd.flags.ack():
            return NextSocketAction.CONTINUE

        res = CmdPing(cmd.stream_id, H2Flags(H2Flags.FLAGS_ACK), cmd.opaque_data)
        self.protocol_handler.post(res)
        return NextSocketAction.CONTINUE

    def handle_rst_stream(self, cmd):
        BayLog.debug("%s received RstStream: stmid=%d code=%d desc=%s",
                     self.ship(), cmd.stream_id, cmd.error_code, H2ErrorCode.msg.get(str(cmd.error_code)))
        return NextSocketAction.CONTINUE


    #
    # private
    #
    @staticmethod
    def _has_upper_case(s):
        if s is None:
            return False
        for c in s:
            if 'A' <= c <= 'Z':
                return True
        return False

    def get_tour(self, key):
        return self.ship().get_tour(key)

    def end_req_content(self, check_id, tur):
        tur.req.end_content(check_id)

    def start_tour(self, tur):
        HttpUtil.parse_host_port(tur, 443 if self.ship().port_docker.secure else 80)
        HttpUtil.parse_authorization(tur)

        tur.req.protocol = self.http_protocol

        skt = self.ship().rudder.key()
        client_adr = tur.req.headers.get_fast(Headers.X_FORWARDED_FOR)
        if client_adr is not None:
            tur.req.remote_address = client_adr
            tur.req.remote_port = None
        else:
            try:
                remote_addr = skt.getpeername()
                tur.req.remote_address = remote_addr[0]
                tur.req.remote_port = remote_addr[1]
            except OSError as e:
                # Maybe connection closed
                BayLog.warn("%s Cannot get peer info (Ignore): %s", self, e)

        tur.req.remote_host_func = lambda: HttpUtil.resolve_remote_host(tur.req.remote_address)

        try:
            server_addr = skt.getsockname()
            tur.req.server_address = server_addr[0]
            tur.req.server_port = server_addr[1]

        except BaseException as e:
            BayLog.error_e(e, traceback.format_stack())
            BayLog.debug("%s Caught error (Continue)", self.ship)


        tur.req.server_port = tur.req.req_port
        tur.req.server_name = tur.req.req_host
        tur.is_secure = self.ship().get_port_docker().secure()

        tur.go()
