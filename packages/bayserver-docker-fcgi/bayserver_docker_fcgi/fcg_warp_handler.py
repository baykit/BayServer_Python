import datetime

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.common.warp_handler import WarpHandler
from bayserver_core.common.warp_ship import WarpShip
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.sink import Sink

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.tour.tour import Tour
from bayserver_core.common.warp_data import WarpData

from bayserver_core.util.char_util import CharUtil
from bayserver_core.util.headers import Headers
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.cgi_util import CgiUtil
from bayserver_core.util.data_consume_listener import DataConsumeListener

from bayserver_docker_fcgi.fcg_command_unpacker import FcgCommandUnPacker
from bayserver_docker_fcgi.fcg_handler import FcgHandler
from bayserver_docker_fcgi.fcg_packet_unpacker import FcgPacketUnPacker

from bayserver_docker_fcgi.fcg_protocol_handler import FcgProtocolHandler
from bayserver_docker_fcgi.command.cmd_stdin import CmdStdIn
from bayserver_docker_fcgi.command.cmd_begin_request import CmdBeginRequest
from bayserver_docker_fcgi.command.cmd_params import CmdParams
from bayserver_docker_fcgi.fcg_params import FcgParams

class FcgWarpHandler(WarpHandler, FcgHandler):
    class WarpProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            ib_handler = FcgWarpHandler()
            cmd_unpacker = FcgCommandUnPacker(ib_handler)
            pkt_unpacker = FcgPacketUnPacker(pkt_store, cmd_unpacker)
            pkt_packer = PacketPacker()
            cmd_packer = CommandPacker(pkt_packer, pkt_store)

            proto_handler = FcgProtocolHandler(ib_handler, pkt_unpacker, pkt_packer, cmd_unpacker, cmd_packer, False)
            ib_handler.init(proto_handler)
            return proto_handler

    STATE_READ_HEADER = 1
    STATE_READ_CONTENT = 2

    cur_warp_id: int
    state: int
    line_buf: bytearray
    pos: int
    last: int
    data: bytearray
    proto_handler: FcgProtocolHandler


    def __init__(self):
        self.cur_warp_id = 0

        self.state = None
        self.line_buf = bytearray()
        self.pos = None
        self.last = None
        self.data = None
        self.reset()

    def init(self, ph: FcgProtocolHandler):
        self.proto_handler = ph

    def ship(self) -> WarpShip:
        return self.proto_handler.ship

    def reset(self):
        super().reset()
        self.reset_state()
        self.line_buf.clear()
        self.pos = 0
        self.last = 0
        self.data = None


    ######################################################
    # Implements WarpHandler
    ######################################################
    def next_warp_id(self):
        self.cur_warp_id += 1
        return self.cur_warp_id

    def new_warp_data(self, warp_id):
        return WarpData(self.ship(), warp_id)

    def send_req_headers(self, tur):
        self.send_begin_req(tur)
        self.send_params(tur)

    def send_req_contents(self, tur: Tour, buf: bytearray, start: int, length: int, lis: DataConsumeListener):
        self.send_stdin(tur, buf, start, length, lis)

    def send_end_req(self, tur: Tour, keep_alive: bool, lis: DataConsumeListener):
        self.send_stdin(tur, None, 0, 0, lis)

    def verify_protocol(self, proto: str):
        pass

    def on_protocol_error(self, e: Exception) -> bool:
        raise Sink()

    ######################################################
    # Implements FcgCommandHandler
    ######################################################

    def handle_begin_request(self, cmd):
        raise ProtocolException("Invalid FCGI command: %d", cmd.type)

    def handle_end_request(self, cmd):
        tur = self.ship().get_tour(cmd.req_id)
        self.end_req_content(tur)
        return NextSocketAction.CONTINUE

    def handle_params(self, cmd):
        raise ProtocolException("Invalid FCGI command: %d", cmd.type)

    def handle_stderr(self, cmd):
        msg = cmd.data[cmd.start: cmd.start + cmd.length + 1]
        BayLog.error("%s server error: %s", self, msg)
        return NextSocketAction.CONTINUE

    def handle_stdin(self, cmd):
        raise ProtocolException("Invalid FCGI command: %d", cmd.type)

    def handle_stdout(self, cmd):
        BayLog.debug("%s handle_stdout req_id=%d len=%d", self.ship, cmd.req_id, cmd.length)

        tur = self.ship().get_tour(cmd.req_id)
        if tur is None:
            raise Sink("Tour not found")

        if cmd.length == 0:
            # stdout end
            self.reset_state()
            return NextSocketAction.CONTINUE

        self.data = cmd.data
        self.pos = cmd.start
        self.last = cmd.start + cmd.length

        if self.state == FcgWarpHandler.STATE_READ_HEADER:
            self.read_header(tur)

        if self.pos < self.last:
            BayLog.debug("%s fcgi: pos=%d last=%d len=%d", self.ship, self.pos, self.last, self.last - self.pos)
            if self.state == FcgWarpHandler.STATE_READ_CONTENT:
                available = tur.res.send_res_content(Tour.TOUR_ID_NOCHECK, self.data, self.pos, self.last - self.pos)
                if not available:
                    return NextSocketAction.SUSPEND

        return NextSocketAction.CONTINUE

    ######################################################
    # Custom methods
    ######################################################
    def read_header(self, tur: Tour):
        wdat = WarpData.get(tur)

        header_finished = self.parse_header(wdat.res_headers)
        if header_finished:
            wdat.res_headers.copy_to(tur.res.headers)

            # Check HTTP Status from headers
            status = wdat.res_headers.get(Headers.STATUS)
            if StringUtil.is_set(status):
                stlist = status.split(" ")
                tur.res.headers.status = int(stlist[0])
                tur.res.headers.remove(Headers.STATUS)


            BayLog.debug("%s fcgi: read header status=%d contlen=%d", self.ship, tur.res.headers.status, wdat.res_headers.content_length())
            sid = self.ship().ship_id

            def callback(length: int, resume: bool):
                if resume:
                    self.ship().resume_read(sid)

            tur.res.set_res_consume_listener(callback)

            tur.res.send_res_headers(Tour.TOUR_ID_NOCHECK)
            self.change_state(FcgWarpHandler.STATE_READ_CONTENT)

    def read_content(self, tur: Tour):
        tur.res.send_res_content(Tour.TOUR_ID_NOCHECK, self.data, self.pos, self.last - self.pos)

    def parse_header(self, headers):

        while True:
            if self.pos == self.last:
                # no byte data
                break

            c = self.data[self.pos]
            self.pos += 1

            if c == CharUtil.CR_BYTE:
                continue
            elif c == CharUtil.LF_BYTE:
                line = StringUtil.from_bytes(self.line_buf)

                if len(line) == 0:
                    return True

                colon_pos = line.find(':')
                if colon_pos == -1:
                    raise ProtocolException("fcgi: Header line of server is invalid: %s", line)
                else:
                    name = line[0:colon_pos].strip()
                    value = line[colon_pos + 1:].strip()

                    if StringUtil.is_empty(name) or StringUtil.is_empty(value):
                        raise ProtocolException("fcgi: Header line of server is invalid: %s", line)

                    headers.add(name, value)
                    if BayServer.harbor.trace_header():
                        BayLog.info("%s fcgi_warp: resHeader: %s=%s", self.ship, name, value)

                self.line_buf.clear()

            else:
                self.line_buf.append(c)

        return False

    def end_req_content(self, tur: Tour):
        self.ship().end_warp_tour(tur)
        tur.res.end_res_content(Tour.TOUR_ID_NOCHECK)
        self.reset_state()

    def change_state(self, new_state: int):
        self.state = new_state

    def reset_state(self):
        self.change_state(self.STATE_READ_HEADER)

    def send_stdin(self, tur, data, ofs, length, callback):
        cmd = CmdStdIn(WarpData.get(tur).warp_id, data, ofs, length)
        self.ship().post(cmd, callback)

    def send_begin_req(self, tur):
        cmd = CmdBeginRequest(WarpData.get(tur).warp_id)
        cmd.role = CmdBeginRequest.FCGI_RESPONDER
        cmd.keep_conn = True
        self.ship().post(cmd)

    def send_params(self, tur: Tour):
        script_base = self.ship().docker.script_base
        if script_base is None:
            script_base = tur.town.location

        if StringUtil.is_empty(script_base):
            raise RuntimeError(f"{tur.town} Could not create SCRIPT_FILENAME. Location of town not specified.")

        doc_root = self.ship().docker.doc_root
        if doc_root is None:
            doc_root = tur.town.location

        if StringUtil.is_empty(doc_root):
            raise RuntimeError(f"{tur.town} docRoot of fcgi docker or location of town is not specified.")

        warp_id = WarpData.get(tur).warp_id
        cmd = CmdParams(warp_id)
        script_fname = [None]

        def callback(name, value):
            if name == CgiUtil.SCRIPT_FILENAME:
                script_fname[0] = value
            else:
                cmd.add_param(name, value)

        CgiUtil.get_env(tur.town.name, doc_root, script_base, tur, callback)

        script_fname = f"proxy:fcgi://{self.ship().docker.host()}:{self.ship().docker.port()}{script_fname[0]}"
        cmd.add_param(CgiUtil.SCRIPT_FILENAME, script_fname[0])

        # Add FCGI params
        cmd.add_param(FcgParams.CONTEXT_PREFIX, "")
        cmd.add_param(FcgParams.UNIQUE_ID, str(datetime.time()))
        # cmd.add_param(FcgParams.X_FORWARDED_FOR, tur.req.remote_address)
        # cmd.add_param(FcgParams.X_FORWARDED_PROTO, tur.is_secure ? "https" : "http")
        # cmd.add_param(FcgParams.X_FORWARDED_PORT, tur.req.req_port.to_s)

        if BayServer.harbor.trace_header():
            for kv in cmd.params:
                BayLog.info("%s fcgi_warp: env: %s=%s", self.ship, kv[0], kv[1])

        self.ship().post(cmd)

        cmd_params_end = CmdParams(WarpData.get(tur).warp_id)
        self.ship().post(cmd_params_end)




