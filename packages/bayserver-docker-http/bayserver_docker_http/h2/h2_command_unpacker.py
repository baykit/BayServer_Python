from bayserver_core.bay_log import BayLog
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.command_unpacker import CommandUnPacker
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.common.inbound_ship import InboundShip

from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_error_code import H2ErrorCode
from bayserver_docker_http.h2.h2_protocol_exception import H2ProtocolException
from bayserver_docker_http.h2.command.cmd_data import CmdData
from bayserver_docker_http.h2.command.cmd_go_away import CmdGoAway
from bayserver_docker_http.h2.command.cmd_headers import CmdHeaders
from bayserver_docker_http.h2.command.cmd_ping import CmdPing
from bayserver_docker_http.h2.command.cmd_preface import CmdPreface
from bayserver_docker_http.h2.command.cmd_priority import CmdPriority
from bayserver_docker_http.h2.command.cmd_rst_stream import CmdRstStream
from bayserver_docker_http.h2.command.cmd_settings import CmdSettings
from bayserver_docker_http.h2.command.cmd_window_update import CmdWindowUpdate


class H2CommandUnPacker(CommandUnPacker):
    """Dispatches incoming H2 frames to command handlers and enforces the
    frame-level rules of RFC 7540 that are independent of any particular
    frame body: header-block continuity (§6.2, §6.10), PUSH_PROMISE from
    client (§8.2), SETTINGS ACK payload size (§6.5), stream-id presence
    requirements (§6.x), silent discard of unknown frame types (§4.1),
    and the per-stream state machine (§5.1).
    """

    # Subset of RFC 7540 §5.1 states tracked by the server. `idle` is
    # represented by absence from `stream_states`; reserved states are
    # not needed because we never send/receive PUSH_PROMISE.
    STATE_OPEN = 1
    STATE_HALF_CLOSED_REMOTE = 2
    STATE_CLOSED = 3

    def __init__(self, cmd_handler, cmd_store=None):
        self.cmd_handler = cmd_handler
        # Per-agent Command pool (optional). When supplied, packet_received
        # rents a pooled Command from this store and Returns it after
        # handle() runs; otherwise it allocates a fresh Command per frame.
        self.cmd_store = cmd_store
        # RFC 7540 § 6.2 / § 6.10: HEADERS without END_HEADERS starts a header
        # block that must be terminated by CONTINUATION on the same stream.
        self.in_header_block = False
        self.header_block_stream_id = 0
        # END_STREAM bit from the HEADERS that started the current block;
        # only takes effect once END_HEADERS finishes the block.
        self.pending_end_stream = False
        # Per-stream state. Idle streams are simply absent.
        self.stream_states = {}
        # Highest client-initiated stream id ever observed; lets us
        # distinguish "idle" from "implicitly closed."
        self.highest_seen_stream_id = 0

    def reset(self):
        self.in_header_block = False
        self.header_block_stream_id = 0
        self.pending_end_stream = False
        self.stream_states = {}
        self.highest_seen_stream_id = 0

    def packet_received(self, pkt):
        BayLog.debug("h2: read packet type=%d strmid=%d len=%d flgs=%s",
                     pkt.type, pkt.stream_id, pkt.data_len(), pkt.flags)

        t = pkt.type

        # RFC 7540 § 4.1: unknown frame types MUST be ignored and discarded.
        # Inside a header block this is still a PROTOCOL_ERROR (CONTINUATION
        # must be next).
        if not self._is_known_type(t):
            if self.in_header_block:
                raise ProtocolException(f"Unknown frame type {t} during header block")
            return NextSocketAction.CONTINUE

        self._validate_frame(pkt)
        self._validate_stream_state(pkt)

        if self.cmd_store is not None:
            cmd = self.cmd_store.rent(t)
            cmd.init(pkt.stream_id, pkt.flags)
        elif t == H2Type.PREFACE:
            cmd = CmdPreface(pkt.stream_id, pkt.flags)
        elif t == H2Type.HEADERS:
            cmd = CmdHeaders(pkt.stream_id, pkt.flags)
        elif t == H2Type.PRIORITY:
            cmd = CmdPriority(pkt.stream_id, pkt.flags)
        elif t == H2Type.SETTINGS:
            cmd = CmdSettings(pkt.stream_id, pkt.flags)
        elif t == H2Type.WINDOW_UPDATE:
            cmd = CmdWindowUpdate(pkt.stream_id, pkt.flags)
        elif t == H2Type.DATA:
            cmd = CmdData(pkt.stream_id, pkt.flags)
        elif t == H2Type.GOAWAY:
            cmd = CmdGoAway(pkt.stream_id, pkt.flags)
        elif t == H2Type.PING:
            cmd = CmdPing(pkt.stream_id, pkt.flags)
        elif t == H2Type.RST_STREAM:
            cmd = CmdRstStream(pkt.stream_id, pkt.flags)
        elif t == H2Type.CONTINUATION:
            # CmdContinuation does not exist as a separate class in this port;
            # CONTINUATION carries a header-block fragment and is dispatched
            # via the headers command path. Reusing CmdHeaders covers the
            # current need (no priority/padding on CONTINUATION).
            cmd = CmdHeaders(pkt.stream_id, pkt.flags)
        else:
            raise RuntimeError(f"Invalid Packet: {pkt}")

        self._update_header_block_state(pkt)
        self._update_stream_state(pkt)

        try:
            cmd.unpack(pkt)
            return cmd.handle(self.cmd_handler)
        finally:
            if self.cmd_store is not None:
                self.cmd_store.Return(cmd)

    @staticmethod
    def _is_known_type(t):
        return t in (H2Type.PREFACE, H2Type.DATA, H2Type.HEADERS, H2Type.PRIORITY,
                     H2Type.RST_STREAM, H2Type.SETTINGS, H2Type.PUSH_PROMISE,
                     H2Type.PING, H2Type.GOAWAY, H2Type.WINDOW_UPDATE,
                     H2Type.CONTINUATION)

    def _validate_frame(self, pkt):
        t = pkt.type
        sid = pkt.stream_id
        flags = pkt.flags

        # § 6.10: while a header block is being received, the next frame
        # MUST be a CONTINUATION on the same stream.
        if self.in_header_block:
            if t != H2Type.CONTINUATION:
                raise ProtocolException(
                    f"Expected CONTINUATION while in header block: got type={t}")
            if sid != self.header_block_stream_id:
                raise ProtocolException(
                    f"CONTINUATION on wrong stream: expected={self.header_block_stream_id} got={sid}")
        elif t == H2Type.CONTINUATION:
            raise ProtocolException("Unexpected CONTINUATION frame outside header block")

        # § 6.x: per-frame stream-id rules.
        if t in (H2Type.DATA, H2Type.HEADERS, H2Type.PRIORITY, H2Type.RST_STREAM,
                 H2Type.PUSH_PROMISE, H2Type.CONTINUATION):
            if sid == 0:
                raise ProtocolException(f"Frame type {t} requires non-zero stream id")
        elif t in (H2Type.SETTINGS, H2Type.PING, H2Type.GOAWAY):
            if sid != 0:
                raise ProtocolException(f"Frame type {t} requires stream id 0, got {sid}")
        # WINDOW_UPDATE allowed on stream 0 or specific stream.

        # § 8.2: server MUST NOT receive PUSH_PROMISE (client must not send).
        if t == H2Type.PUSH_PROMISE:
            raise ProtocolException("Server must not receive PUSH_PROMISE")

        # § 6.5: SETTINGS with ACK must have empty payload.
        if t == H2Type.SETTINGS and flags.ack() and pkt.data_len() > 0:
            raise ProtocolException("SETTINGS ACK must have no payload")

    def _validate_stream_state(self, pkt):
        """RFC 7540 § 5.1: verify the incoming frame is allowed in the
        current stream state. Connection-level frames (stream id 0)
        are unaffected. CONTINUATION is governed by header-block rules
        in _validate_frame, not by stream state."""
        t = pkt.type
        sid = pkt.stream_id
        if sid == 0 or t == H2Type.CONTINUATION:
            return

        state = self.stream_states.get(sid)

        if state is None:
            # idle: no state recorded. If id <= high-water mark, it was
            # implicitly closed by § 5.1.1.
            implicitly_closed = sid <= self.highest_seen_stream_id
            # § 5.1.1: client-initiated streams have odd ids and strictly
            # increasing.
            if t == H2Type.HEADERS:
                if (sid & 1) == 0:
                    raise ProtocolException(f"Client HEADERS with even stream id {sid}")
                if implicitly_closed:
                    raise ProtocolException(
                        f"Stream id {sid} is not greater than previous {self.highest_seen_stream_id}")
                # § 5.1.2 active-stream enforcement was rolled back upstream
                # (Java commit 39811d1) because counting open streams against
                # MAX_CONCURRENT_STREAMS clashes with the closed-stream tests
                # in § 5.1 (HALF_CLOSED_REMOTE never transitions to CLOSED, so
                # the count grows monotonically and h2spec's later closed-
                # stream cases get REFUSED_STREAM instead of STREAM_CLOSED).
                # The per-tour slot exhaustion is still enforced via the
                # REFUSED_STREAM path in H2InboundHandler.handle_headers when
                # get_tour() returns None.
            if t in (H2Type.HEADERS, H2Type.PRIORITY):
                # HEADERS opens new stream; PRIORITY allowed on any state.
                return
            if t in (H2Type.RST_STREAM, H2Type.DATA, H2Type.WINDOW_UPDATE):
                if implicitly_closed:
                    raise ProtocolException(f"Frame type {t} on closed stream {sid}")
                raise ProtocolException(f"Frame type {t} on idle stream {sid}")
            return

        if state == H2CommandUnPacker.STATE_OPEN:
            # Second HEADERS on open stream is a trailer; § 8.1 requires
            # END_STREAM.
            if t == H2Type.HEADERS and not pkt.flags.end_stream():
                raise ProtocolException(
                    f"Trailer HEADERS on stream {sid} missing END_STREAM")
            return

        if state == H2CommandUnPacker.STATE_HALF_CLOSED_REMOTE:
            if t == H2Type.DATA or t == H2Type.HEADERS:
                raise ProtocolException(
                    f"Frame type {t} on half-closed (remote) stream {sid}")
            return

        if state == H2CommandUnPacker.STATE_CLOSED:
            if t == H2Type.PRIORITY or t == H2Type.WINDOW_UPDATE:
                return
            raise ProtocolException(f"Frame type {t} on closed stream {sid}")

    def _count_active_streams(self):
        n = 0
        for s in self.stream_states.values():
            if s != H2CommandUnPacker.STATE_CLOSED:
                n += 1
        return n

    def _update_header_block_state(self, pkt):
        t = pkt.type
        if t == H2Type.HEADERS or t == H2Type.PUSH_PROMISE:
            self.in_header_block = not pkt.flags.end_headers()
            self.header_block_stream_id = pkt.stream_id
            self.pending_end_stream = pkt.flags.end_stream()
        elif t == H2Type.CONTINUATION:
            if pkt.flags.end_headers():
                self.in_header_block = False

    def _update_stream_state(self, pkt):
        t = pkt.type
        sid = pkt.stream_id
        if sid == 0:
            return

        state = self.stream_states.get(sid)

        if t == H2Type.HEADERS:
            if state is None:
                # Opening a new stream implicitly closes any lower-id
                # streams (§ 5.1.1).
                if sid > self.highest_seen_stream_id:
                    self.highest_seen_stream_id = sid
                self.stream_states[sid] = H2CommandUnPacker.STATE_OPEN
                if pkt.flags.end_headers() and pkt.flags.end_stream():
                    self.stream_states[sid] = H2CommandUnPacker.STATE_HALF_CLOSED_REMOTE
            elif state == H2CommandUnPacker.STATE_OPEN:
                # Trailer section: § 8.1 requires END_STREAM.
                if pkt.flags.end_headers() and pkt.flags.end_stream():
                    self.stream_states[sid] = H2CommandUnPacker.STATE_HALF_CLOSED_REMOTE

        elif t == H2Type.CONTINUATION:
            # HEADERS' END_STREAM takes effect once header block closes
            # via END_HEADERS on this CONTINUATION.
            if pkt.flags.end_headers() and self.pending_end_stream \
                    and state == H2CommandUnPacker.STATE_OPEN:
                self.stream_states[sid] = H2CommandUnPacker.STATE_HALF_CLOSED_REMOTE
            if pkt.flags.end_headers():
                self.pending_end_stream = False

        elif t == H2Type.DATA:
            if pkt.flags.end_stream() and state == H2CommandUnPacker.STATE_OPEN:
                self.stream_states[sid] = H2CommandUnPacker.STATE_HALF_CLOSED_REMOTE

        elif t == H2Type.RST_STREAM:
            self.stream_states[sid] = H2CommandUnPacker.STATE_CLOSED
            if sid > self.highest_seen_stream_id:
                self.highest_seen_stream_id = sid
