import traceback
from typing import List

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.common.warp_data import WarpData
from bayserver_core.common.warp_handler import WarpHandler
from bayserver_core.common.warp_ship import WarpShip
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.sink import Sink
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus

from bayserver_docker_http.h2.command.cmd_data import CmdData
from bayserver_docker_http.h2.command.cmd_headers import CmdHeaders
from bayserver_docker_http.h2.command.cmd_ping import CmdPing
from bayserver_docker_http.h2.command.cmd_preface import CmdPreface
from bayserver_docker_http.h2.command.cmd_settings import CmdSettings
from bayserver_docker_http.h2.command.cmd_window_update import CmdWindowUpdate
from bayserver_docker_http.h2.h2_command_unpacker import H2CommandUnPacker
from bayserver_docker_http.h2.h2_flags import H2Flags
from bayserver_docker_http.h2.h2_packet import H2Packet
from bayserver_docker_http.h2.h2_packet_unpacker import H2PacketUnPacker
from bayserver_docker_http.h2.h2_protocol_handler import H2ProtocolHandler
from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_handler import H2Handler
from bayserver_docker_http.h2.header_block import HeaderBlock
from bayserver_docker_http.h2.header_block_analyzer import HeaderBlockAnalyzer
from bayserver_docker_http.h2.header_block_builder import HeaderBlockBuilder
from bayserver_docker_http.h2.header_table import HeaderTable


# 16 MiB advertised stream + connection window. Above any single bench body;
# reactive WINDOW_UPDATEs in handle_data top it back up.
INITIAL_WINDOW_SIZE_OUT = 16 * 1024 * 1024


class H2WarpHandler(H2Handler, WarpHandler):

    class WarpProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            warp_handler = H2WarpHandler()
            cmd_unpacker = H2CommandUnPacker(warp_handler)
            # server_mode=False on the warp side: we send the preface, we
            # never expect to receive one.
            pkt_unpacker = H2PacketUnPacker(cmd_unpacker, pkt_store, False)
            pkt_packer = PacketPacker()
            cmd_packer = CommandPacker(pkt_packer, pkt_store)
            proto_handler = H2ProtocolHandler(
                warp_handler, pkt_unpacker, pkt_packer,
                cmd_unpacker, cmd_packer, False)
            warp_handler.init(proto_handler)
            return proto_handler

    def __init__(self):
        super().__init__()
        self.protocol_handler = None
        self.analyzer = HeaderBlockAnalyzer()
        self.req_header_tbl = HeaderTable.create_dynamic_table()
        self.res_header_tbl = HeaderTable.create_dynamic_table()
        # Client-initiated H2 streams use odd ids: 1, 3, 5, ...
        self.cur_stream_id = 1
        # True once the H2 connection prelude (PRI preface + initial SETTINGS)
        # has been pushed onto the wire. Sent lazily on the first
        # send_req_headers call so we don't need a notify_connect hook on
        # this handler.
        self.prelude_sent = False

    def init(self, ph: H2ProtocolHandler):
        self.protocol_handler = ph

    def ship(self) -> WarpShip:
        return self.protocol_handler.ship

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        super().reset()
        self.cur_stream_id = 1
        self.prelude_sent = False

    ######################################################
    # Implements H2CommandHandler
    ######################################################

    def handle_preface(self, cmd):
        # Client side never receives a preface: only servers do.
        raise Sink()

    def handle_data(self, cmd):
        tur = self.ship().get_tour(cmd.stream_id)
        available = tur.res.send_res_content(
            Tour.TOUR_ID_NOCHECK, cmd.data, cmd.start, cmd.length)

        # Replenish flow-control windows so the upstream backend can keep
        # sending. Without this the connection-level + stream-level windows
        # (default 65535 each) drain after ~65 KB of body and the backend
        # stops sending DATA frames; multi-chunk responses (>= 100 KB) hang
        # until timeout.
        if cmd.length > 0:
            stream_upd = CmdWindowUpdate(cmd.stream_id)
            stream_upd.window_size_increment = cmd.length
            conn_upd = CmdWindowUpdate(0)
            conn_upd.window_size_increment = cmd.length
            self.ship().post(stream_upd)
            self.ship().post(conn_upd)

        if not available:
            return NextSocketAction.SUSPEND

        if cmd.flags.end_stream():
            self._end_res_content(tur)

        return NextSocketAction.CONTINUE

    def handle_headers(self, cmd):
        tur = self.ship().get_tour(cmd.stream_id)
        if tur is None:
            BayLog.error("%s no tour for streamId=%d", self.ship(), cmd.stream_id)
            return NextSocketAction.CONTINUE
        wtur = WarpData.get(tur)

        if tur.res.header_sent:
            raise ProtocolException("Header command not expected")

        try:
            header_blocks = self._parse_header_blocks(
                bytes(cmd.data[cmd.start:cmd.start + cmd.length]))
        except (IndexError, ValueError, KeyError, IOError) as e:
            raise ProtocolException(f"HPACK decode failed: {e}")

        for blk in header_blocks:
            if blk.op == HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE:
                self.res_header_tbl.set_size(blk.size)
                continue
            self.analyzer.analyze_header_block(blk, self.res_header_tbl)
            if self.analyzer.name is None:
                continue

            name = self.analyzer.name
            value = self.analyzer.value
            if name[0] != ':':
                tur.res.headers.add(name, value)
            elif name == HeaderTable.PSEUDO_HEADER_STATUS:
                try:
                    tur.res.headers.set_status(int(value))
                except ValueError as e:
                    BayLog.error_e(e, traceback.format_stack())
            # other pseudo-headers in a response are protocol errors per RFC,
            # but we ignore them here since the warp peer is trusted.

        if cmd.flags.end_headers():
            tur.res.send_res_headers(Tour.TOUR_ID_NOCHECK)

            # Wire up the back-pressure resume hook (mirrors H1WarpHandler):
            # the consumer listener fires when the downstream write buffer
            # drains; on resume=True we ask the warp ship to read more from
            # the backend. Without this, send_res_content's internal
            # consumed() callback finds res_consume_listener=None and tears
            # the agent down with "Consume listener is null".
            if not cmd.flags.end_stream():
                wsip = self.ship()
                sid = wsip.id()

                def _resume_cb(length, resume):
                    if resume:
                        wsip.resume_read(sid)

                tur.res.set_res_consume_listener(_resume_cb)

            if cmd.flags.end_stream():
                self._end_res_content(tur)

        return NextSocketAction.CONTINUE

    def handle_priority(self, cmd):
        # PRIORITY frames are deprecated in RFC 9113; we don't act on them.
        return NextSocketAction.CONTINUE

    def handle_settings(self, cmd):
        if not cmd.flags.ack():
            res = CmdSettings(0, H2Flags(H2Flags.FLAGS_ACK))
            self.protocol_handler.command_packer.post(self.ship(), res)
        return NextSocketAction.CONTINUE

    def handle_window_update(self, cmd):
        return NextSocketAction.CONTINUE

    def handle_go_away(self, cmd):
        BayLog.error("%s received GoAway: code=%s debug=%s",
                     self.ship(), cmd.error_code, cmd.debug_data)
        self.ship().notify_service_unavailable("Received GoAway packet")
        return NextSocketAction.CLOSE

    def handle_ping(self, cmd):
        res = CmdPing(cmd.stream_id, H2Flags(H2Flags.FLAGS_ACK), cmd.opaque_data)
        self.protocol_handler.command_packer.post(self.ship(), res)
        return NextSocketAction.CONTINUE

    def handle_rst_stream(self, cmd):
        tur = self.ship().get_tour(cmd.stream_id, must=False)
        if cmd.error_code != 0 and tur is not None:
            BayLog.error("%s received RstStream: code=%s", self.ship(),
                         cmd.error_code)
            try:
                tur.res.send_error(Tour.TOUR_ID_NOCHECK,
                                   HttpStatus.SERVICE_UNAVAILABLE,
                                   "Received RstStream packet")
            except Exception as e:
                BayLog.error_e(e, traceback.format_stack())
        return NextSocketAction.CONTINUE

    ######################################################
    # Implements WarpHandler
    ######################################################

    def next_warp_id(self):
        cur = self.cur_stream_id
        self.cur_stream_id += 2
        return cur

    def new_warp_data(self, warp_id):
        return WarpData(self.ship(), warp_id)

    def send_req_headers(self, tur):
        self._send_prelude_if_needed()
        self._send_req_header_command(tur)

    def send_req_contents(self, tur, buf, start, length, lis):
        stream_id = WarpData.get(tur).warp_id
        cmd = CmdData(stream_id, None, buf, start, length)
        self.ship().post(cmd, lis)

    def send_end_req(self, tur, keep_alive, lis):
        # No-op when the request had no body: _send_req_header_command
        # already carried END_STREAM on the HEADERS frame, so an extra
        # empty DATA frame would land on a half-closed (remote) stream
        # and the backend would reject it with PROTOCOL_ERROR.
        if (not tur.req.headers.contains("content-length")
                and not tur.req.headers.contains("transfer-encoding")):
            if lis is not None:
                lis()
            return

        stream_id = WarpData.get(tur).warp_id
        cmd = CmdData(stream_id, None, b"", 0, 0)
        cmd.flags.set_end_stream(True)
        # WarpShip.post handles the !connected case via cmd_buf; once the
        # connection is up post forwards to protocolHandler.post under the
        # hood.
        self.ship().post(cmd, lis)

    def verify_protocol(self, proto):
        # No-op: HtpWarpDocker forces H2 from the start, so there's no
        # ALPN-driven protocol switch to verify.
        pass

    ######################################################
    # Implements ProtocolHandler
    ######################################################

    def on_protocol_error(self, err: ProtocolException, stk: List[str]) -> bool:
        raise Sink()

    def req_finished(self):
        # The warp side does not gate stream-end on req_finished; tours end
        # when handle_data sees END_STREAM. Return True so the WarpShip
        # accept loop doesn't block.
        return True

    ######################################################
    # Custom methods
    ######################################################

    def _send_prelude_if_needed(self):
        """Send the H2 connection prelude (RFC 7540 § 3.5):
          1. The 24-byte client connection preface
          2. An initial SETTINGS frame
        Called lazily on the first send_req_headers so it runs after the
        TCP connect completes (= after WarpShip.notify_connect started
        draining queued tours) but before the first request HEADERS go out.
        """
        if self.prelude_sent:
            return

        # 1. Connection preface — empty CmdPreface. Its pack() emits the
        # 24 preface bytes raw (not in H2 frame format).
        # Use ship().post (not protocol_handler.command_packer.post):
        # WarpShip.post buffers commands in cmd_buf while !connected and
        # drains them via flush() after notify_connect.
        preface = CmdPreface(0, None)
        self.ship().post(preface)

        # 2. Initial SETTINGS frame on the control stream (id=0), no ACK.
        # INITIAL_WINDOW_SIZE here only applies to per-stream windows on
        # newly-created streams; the connection-level window starts at the
        # RFC 7540 default of 65535 and can only be bumped via
        # WINDOW_UPDATE on stream 0 (step 3).
        sett = CmdSettings(H2ProtocolHandler.CTL_STREAM_ID)
        sett.stream_id = 0
        max_concurrent = max(BayServer.harbor.max_ships(), 100)
        sett.items.append(CmdSettings.Item(
            CmdSettings.MAX_CONCURRENT_STREAMS, max_concurrent))
        sett.items.append(CmdSettings.Item(
            CmdSettings.INITIAL_WINDOW_SIZE, INITIAL_WINDOW_SIZE_OUT))
        self.ship().post(sett)

        # 3. Connection-level WINDOW_UPDATE: bump stream 0's window from
        # the spec-mandated 65535 to (initial + INITIAL_WINDOW_SIZE_OUT)
        # so multi-MB bodies aren't rate-limited by the connection window
        # before the reactive WINDOW_UPDATEs in handle_data kick in.
        conn_up = CmdWindowUpdate(0)
        conn_up.window_size_increment = INITIAL_WINDOW_SIZE_OUT
        self.ship().post(conn_up)

        self.prelude_sent = True

    def _send_req_header_command(self, tur):
        twn = tur.town
        twn_path = twn.name()
        if not twn_path.endswith("/"):
            twn_path += "/"

        sip = self.ship()
        new_uri = sip.docker.warp_base() + tur.req.uri[len(twn_path):]

        bld = HeaderBlockBuilder()
        header_blocks = []

        header_blocks.append(bld.build_header_block(
            HeaderTable.PSEUDO_HEADER_METHOD, tur.req.method, self.req_header_tbl))
        header_blocks.append(bld.build_header_block(
            HeaderTable.PSEUDO_HEADER_PATH, new_uri, self.req_header_tbl))
        header_blocks.append(bld.build_header_block(
            HeaderTable.PSEUDO_HEADER_SCHEME,
            "https" if tur.is_secure else "http", self.req_header_tbl))
        header_blocks.append(bld.build_header_block(
            HeaderTable.PSEUDO_HEADER_AUTHORITY,
            f"{sip.docker.host()}:{sip.docker.port()}", self.req_header_tbl))

        # Regular request headers: must be lowercase, must not include
        # connection-specific fields (RFC 7540 § 8.1.2.2). The Host header
        # is already covered by :authority above and must not be duplicated.
        for name in tur.req.headers.names():
            lower = name.lower()
            if lower in ("connection", "host", "keep-alive",
                         "transfer-encoding", "upgrade", "proxy-connection"):
                continue
            for value in tur.req.headers.values(name):
                header_blocks.append(bld.build_header_block(
                    lower, value, self.req_header_tbl))

        stream_id = WarpData.get(tur).warp_id
        end_stream = (not tur.req.headers.contains("content-length")
                      and not tur.req.headers.contains("transfer-encoding"))

        # CmdHeaders carries header_blocks directly (its pack() encodes
        # them via HeaderBlock.pack in order). For multi-frame splitting
        # (HEADERS + CONTINUATION) we would need a separate CmdContinuation
        # class; for the bench body sizes used here the encoded block fits
        # in one frame.
        cmd = CmdHeaders(stream_id)
        cmd.excluded = False
        cmd.header_blocks = header_blocks
        cmd.flags.set_end_headers(True)
        if end_stream:
            cmd.flags.set_end_stream(True)
        cmd.flags.set_padded(False)
        sip.post(cmd)

    def _parse_header_blocks(self, raw_bytes):
        """Walk an HPACK header-block fragment via HeaderBlock.unpack —
        same shape as H2InboundHandler._parse_header_blocks. Synthesise
        an H2Packet whose data area holds the bytes so the existing
        H2DataAccessor + HeaderBlock.unpack can be reused."""
        synth = H2Packet(H2Type.HEADERS)
        end = synth.header_len + len(raw_bytes)
        if len(synth.buf) < end:
            synth.buf.extend(bytes(end - len(synth.buf)))
        synth.buf[synth.header_len:end] = raw_bytes
        synth.buf_len = end
        acc = synth.new_h2_data_accessor()
        blocks = []
        while acc.pos < len(raw_bytes):
            blocks.append(HeaderBlock.unpack(acc))
        return blocks

    def _end_res_content(self, tur):
        # H1WarpHandler ordering: end_warp_tour BEFORE end_res_content,
        # since the latter resets the tour and clears WarpData.get(tur).
        self.ship().end_warp_tour(tur, True)
        tur.res.end_res_content(Tour.TOUR_ID_NOCHECK)
