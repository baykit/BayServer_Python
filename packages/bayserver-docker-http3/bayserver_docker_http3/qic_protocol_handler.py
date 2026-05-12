import traceback

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.protocol_handler import ProtocolHandler

from bayserver_docker_http3.command.cmd_data import CmdData
from bayserver_docker_http3.command.cmd_finished import CmdFinished
from bayserver_docker_http3.command.cmd_header import CmdHeader
from bayserver_docker_http3.h3_error_code import H3ErrorCode
from bayserver_docker_http3.qic_packet import QicPacket


class _ReqState:
    READ_HEADER = 1
    READ_CONTENT = 2
    END = 3


class _PartialResponse:
    """Queued outbound chunk for a stream. Mirrors Java's PartialResponse:
    either carries header list (None body), body slice + listener, or a fin
    sentinel. Drained on writability."""

    def __init__(self, headers=None, body=None, ofs=0, fin=False, listener=None):
        self.headers = headers
        if body is not None:
            self.body = bytes(body[ofs:])
        else:
            self.body = None
        self.fin = fin
        self.written = 0
        self.listener = listener
        self.finished = False


class QicProtocolHandler(ProtocolHandler):
    """Per-connection H3 protocol handler. Owns the croute QUIC + H3
    connection, drains poll() events into QicCommand dispatch, and queues
    outgoing headers/body via PartialResponse when streams block."""

    MAX_BUFFER_SIZE = 16384
    PROTOCOL = "HTTP/3"

    def __init__(self, inbound_handler, con, sender,
                 local_address, peer_address, h3_config, multiplexer):
        # Parent ProtocolHandler expects (pkt_unpacker, pkt_packer,
        # cmd_unpacker, cmd_packer, cmd_handler, server_mode). Pass
        # everything as None except the handler — H3 frames are processed
        # via croute, not the standard packet pipeline.
        super().__init__(None, None, None, None, inbound_handler, True)

        self.con = con
        self.sender = sender
        self.local_address = local_address
        self.peer_address = peer_address
        self.h3_config = h3_config
        self.multiplexer = multiplexer

        # stream_id -> list of PartialResponse
        self.partial_responses = {}

        # Reusable scratch state for outbound packets.
        self._send_scratch = bytearray(QicPacket.MAX_DATAGRAM_SIZE)
        from croute.binding import new_send_info
        self._send_info = new_send_info()

        self.ship = None
        self.h3con = None

    def __str__(self):
        return str(self.ship) if self.ship is not None else "QicProtocolHandler"

    def set_ship(self, ship):
        self.ship = ship

    ######################################################
    # Implements ProtocolHandler
    ######################################################

    def protocol(self):
        return "h3"

    def max_req_packet_data_size(self):
        return QicProtocolHandler.MAX_BUFFER_SIZE

    def max_res_packet_data_size(self):
        return QicProtocolHandler.MAX_BUFFER_SIZE

    def bytes_received(self, buf, adr):
        from croute.error import CrouteError
        from croute.binding import ERR_DONE
        from croute.h3 import Connection as H3Connection

        try:
            # croute's Connection.recv takes a bytearray (writable) and
            # the from/to Addresses.
            packet = bytearray(buf)
            n = self.con.recv(packet, self.peer_address, self.local_address)
        except CrouteError as e:
            BayLog.debug("%s recv rejected: %s", self, e)
            return NextSocketAction.CONTINUE

        if n < len(packet):
            BayLog.info("Packet Read failed ? %d/%d", n, len(packet))

        if n == ERR_DONE:
            BayLog.debug("No data")
            return NextSocketAction.CONTINUE

        # Establish H3 connection once QUIC handshake is up.
        if self.h3con is None and (self.con.is_in_early_data() or self.con.is_established()):
            BayLog.debug("%s Handshake done", self)
            try:
                self.h3con = H3Connection(self.con, self.h3_config)
                BayLog.debug("%s New H3 connection", self)
            except CrouteError as e:
                BayLog.error("%s H3 connection setup failed: %s", self, e)
                return NextSocketAction.CONTINUE

        if self.h3con is not None:
            self._process_h3_connection()

        return NextSocketAction.CONTINUE

    ######################################################
    # H3 event dispatch
    ######################################################

    def _dispatch_event(self, ev):
        stm_id = ev.stream_id
        evtype = ev.type
        handler = self.command_handler
        if evtype == "headers":
            handler.handle_headers(CmdHeader(stm_id, ev.headers, False))
        elif evtype == "data":
            handler.handle_data(CmdData(stm_id))
        elif evtype == "finished":
            handler.handle_finished(CmdFinished(stm_id))
        else:
            BayLog.debug("%s stm#%d ignored event: %s", self, stm_id, evtype)

    def _process_h3_connection(self):
        BayLog.trace("%s processH3Connection", self)
        from croute.error import CrouteError
        try:
            while True:
                ev = self.h3con.poll()
                if ev is None:
                    break
                self._dispatch_event(ev)
        except CrouteError as e:
            BayLog.debug("%s h3 poll failed: %s", self, e)

        self._flush_writable()

    def _flush_writable(self):
        for sid in self.con.writable_streams():
            try:
                self._on_stream_writable(sid)
            except Exception as e:
                BayLog.error_e(e, traceback.format_stack())

    def _on_stream_writable(self, stm_id):
        from croute.error import CrouteError

        parts = self.partial_responses.get(stm_id)
        if parts is None:
            return

        BayLog.debug("%s stm#%d writable qlen=%d", self, stm_id, len(parts))
        listeners = []
        try:
            for part in parts:
                if part.headers is not None:
                    try:
                        self.h3con.send_response(stm_id, part.headers, part.fin)
                    except CrouteError as e:
                        if e.code == CrouteError.H3_ERR_STREAM_BLOCKED:
                            BayLog.debug("%s stm#%d retry to send header: blocked", self, stm_id)
                            break
                        else:
                            BayLog.error("%s stm#%d retry header failed: %s", self, stm_id, e)
                            break
                    BayLog.debug("%s stm#%d retry header sent", self, stm_id)
                    part.finished = True
                else:
                    body = part.body[part.written:]
                    try:
                        n = self.h3con.send_body(stm_id, body, part.fin)
                    except CrouteError as e:
                        BayLog.error("%s stm#%d retry body failed: %s", self, stm_id, e)
                        break
                    if n == 0:
                        BayLog.debug("%s stm#%d retry body DONE (no capacity)", self, stm_id)
                        break
                    part.written += n
                    if part.written == len(part.body):
                        part.finished = True
                    else:
                        break

            new_parts = []
            for p in parts:
                if p.finished:
                    if p.listener is not None:
                        listeners.append(p.listener)
                else:
                    new_parts.append(p)
            if new_parts:
                self.partial_responses[stm_id] = new_parts
            else:
                self.partial_responses.pop(stm_id, None)
        except IOError as e:
            BayLog.error_e(e, traceback.format_stack())
            self.partial_responses.pop(stm_id, None)

        for lis in listeners:
            try:
                lis(True, False)
            except Exception as e:
                BayLog.error_e(e, traceback.format_stack())

        self.post_packets()

    def add_partial_response(self, stm_id, part):
        parts = self.partial_responses.get(stm_id)
        if parts is None:
            parts = []
            self.partial_responses[stm_id] = parts
        parts.append(part)

    def post_packets(self):
        from croute.binding import ERR_DONE
        from croute.error import CrouteError

        posted = False
        while True:
            if self.con.is_closed():
                break
            try:
                n = self.con.send(self._send_scratch, self._send_info)
            except CrouteError as e:
                BayLog.debug("%s send on closing connection: %s", self, e)
                break
            if n == ERR_DONE:
                break
            buf = bytes(self._send_scratch[:n])
            adr = (self.sender.ip, self.sender.port)
            self.multiplexer.req_write(self.ship.rudder, buf, adr, None, None)
            posted = True
        return posted

    def is_closed(self):
        return self.con.is_closed()

    def peer_or_local_error_code(self):
        """Look up the underlying QUIC error code after a H3 transport error.
        croute Python doesn't expose a thin wrapper, so use the native
        binding directly. Returns -1 if no error was recorded."""
        try:
            from croute.binding import native
            err_code = [0]
            is_app = [False]
            reason = [None]
            if native.quiche_conn_peer_error(self.con.ptr, is_app, err_code, reason):
                return err_code[0]
            if native.quiche_conn_local_error(self.con.ptr, is_app, err_code, reason):
                return err_code[0]
        except Exception:
            pass
        return -1
