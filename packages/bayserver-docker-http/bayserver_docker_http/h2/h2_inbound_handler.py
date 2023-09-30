import socket

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.http_exception import HttpException

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.tour.tour_store import TourStore
from bayserver_core.tour.tour import Tour
from bayserver_core.tour.tour_req import TourReq
from bayserver_core.watercraft.ship import Ship
from bayserver_core.docker.base.inbound_handler import InboundHandler

from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_util import HttpUtil
from bayserver_core.util.string_util import StringUtil


from bayserver_docker_http.h2.h2_flags import H2Flags
from bayserver_docker_http.h2.h2_error_code import H2ErrorCode
from bayserver_docker_http.h2.h2_protocol_handler import H2ProtocolHandler
from bayserver_docker_http.h2.h2_settings import H2Settings
from bayserver_docker_http.h2.header_block import HeaderBlock
from bayserver_docker_http.h2.header_block_analyzer import HeaderBlockAnalyzer
from bayserver_docker_http.h2.header_block_builder import HeaderBlockBuilder
from bayserver_docker_http.h2.command.cmd_settings import CmdSettings
from bayserver_docker_http.h2.command.cmd_window_update import CmdWindowUpdate
from bayserver_docker_http.h2.command.cmd_ping import CmdPing
from bayserver_docker_http.h2.command.cmd_data import CmdData
from bayserver_docker_http.h2.command.cmd_go_away import CmdGoAway
from bayserver_docker_http.h2.command.cmd_headers import CmdHeaders



class H2InboundHandler(H2ProtocolHandler, InboundHandler):
    class InboundProtocolHandlerFactory:

        def create_protocol_handler(self, pkt_store):
            return H2InboundHandler(pkt_store)


    def __init__(self, pkt_store):
        super().__init__(pkt_store, True)
        self.window_size = BayServer.harbor.tour_buffer_size
        self.settings = H2Settings()
        self.analyzer = HeaderBlockAnalyzer()
        self.req_cont_len = None
        self.req_cont_read = None
        self.header_read = None
        self.window_sizes = None
        self.http_protocol = None


    def ship(self):
        return self.ship

    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        super().reset()
        self.header_read = False
        self.req_cont_len = 0
        self.req_cont_read = 0

    ######################################################
    # implements InboundHandler
    ######################################################

    def send_res_headers(self, tur):
        cmd = CmdHeaders(tur.req.key)
        bld = HeaderBlockBuilder()
        blk = bld.build_header_block(":status", str(tur.res.headers.status), self.res_header_tbl)
        cmd.header_blocks.append(blk)

        # headers
        if BayServer.harbor.trace_header:
            BayLog.info("%s res status: %d", tur, tur.res.headers.status)

        for name in tur.res.headers.names():
            if StringUtil.eq_ignorecase(name, "connection"):
                BayLog.trace("%s Connection header is discarded", tur)
            else:
                for value in tur.res.headers.values(name):
                    if BayServer.harbor.trace_header:
                        BayLog.info("%s H2 res header: %s=%s", tur, name, value)

                    blk = bld.build_header_block(name, value, self.res_header_tbl)
                    cmd.header_blocks.append(blk)

        cmd.flags.set_end_headers(True)
        cmd.excluded = True
        cmd.flags.set_padded(False)
        self.command_packer.post(self.ship, cmd)

    def send_res_content(self, tur, bytes, ofs, length, callback):
        cmd = CmdData(tur.req.key, None, bytes, ofs, length)
        self.command_packer.post(self.ship, cmd, callback)

    def send_end_tour(self, tur, keep_alive, callback):
        cmd = CmdData(tur.req.key, None, [], 0, 0)
        cmd.flags.set_end_stream(True)
        self.command_packer.post(self.ship, cmd, callback)

    def send_req_protocol_error(self, err):
        BayLog.error_e(err)

        cmd = CmdGoAway(H2ProtocolHandler.CTL_STREAM_ID)
        cmd.stream_id = H2ProtocolHandler.CTL_STREAM_ID
        cmd.last_stream_id = H2ProtocolHandler.CTL_STREAM_ID
        cmd.error_code = H2ErrorCode.PROTOCOL_ERROR
        cmd.debug_data = b"Thank you!"
        try:
            self.command_packer.post(self.ship, cmd)
            self.command_packer.end(self.ship)
        except IOError as e:
            BayLog.error_e(e)
        return False

    ######################################################
    # implements H2CommandHandler
    ######################################################

    def handle_preface(self, cmd):
        BayLog.debug("%s h2: handle_preface: proto=%s", self.ship, cmd.protocol)

        self.http_protocol = cmd.protocol

        sett = CmdSettings(H2ProtocolHandler.CTL_STREAM_ID)
        sett.stream_id = 0
        sett.items.append(CmdSettings.Item(CmdSettings.MAX_CONCURRENT_STREAMS, TourStore.MAX_TOURS))
        sett.items.append(CmdSettings.Item(CmdSettings.INITIAL_WINDOW_SIZE, self.window_size))
        self.command_packer.post(self.ship, sett)

        sett = CmdSettings(H2ProtocolHandler.CTL_STREAM_ID)
        sett.stream_id = 0
        sett.flags.set_ack(True)

        return NextSocketAction.CONTINUE

    def handle_headers(self, cmd):
        BayLog.debug("%s handle_headers: stm=%d dep=%d weight=%d", self.ship, cmd.stream_id, cmd.stream_dependency,
                     cmd.weight)

        tur = self.get_tour(cmd.stream_id)
        if tur is None:
            BayLog.error(BayMessage.get(Symbol.INT_NO_MORE_TOURS))
            tur = self.ship.get_tour(cmd.stream_id, True)
            tur.res.s_error(Tour.TOUR_ID_NOCHECK, HttpStatus.SERVICE_UNAVAILABLE, "No available tours")
            return NextSocketAction.CONTINUE

        for blk in cmd.header_blocks:
            if blk.op == HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE:
                BayLog.trace("%s header block update table size: %d", tur, blk.size)
                self.req_header_tbl.set_size(blk.size)
                continue

            self.analyzer.analyze_header_block(blk, self.req_header_tbl)
            if BayServer.harbor.trace_header:
                BayLog.info("%s req header: %s=%s :%s", tur, self.analyzer.name, self.analyzer.value, blk);

            if self.analyzer.name is None:
                next

            elif self.analyzer.name[0] != ":":
                tur.req.headers.add(self.analyzer.name, self.analyzer.value)

            elif self.analyzer.method is not None:
                tur.req.method = self.analyzer.method

            elif self.analyzer.path is not None:
                tur.req.uri = self.analyzer.path

            elif self.analyzer.scheme is not None:
                pass

            elif self.analyzer.status is not None:
                raise RuntimeError("Illegal State")

        if cmd.flags.end_headers():
            tur.req.protocol = "HTTP/2.0"
            BayLog.debug("%s H2 read header method=%s protocol=%s uri=%s contlen=%d",
                        self.ship, tur.req.method, tur.req.protocol, tur.req.uri, tur.req.headers.content_length())

            req_cont_len = tur.req.headers.content_length()

            if req_cont_len > 0:
                sid = self.ship.ship_id

                def callback(length, resume):
                    self.ship.check_ship_id(sid)
                    if length > 0:
                        upd = CmdWindowUpdate(cmd.stream_id)
                        upd.window_size_increment = length
                        upd2 = CmdWindowUpdate(0)
                        upd2.window_size_increment = length
                        cmd_packer = self.command_packer
                        try:
                            cmd_packer.post(self.ship, upd)
                            cmd_packer.post(self.ship, upd2)
                        except IOError as ex:
                            BayLog.error_e(ex)

                    if resume:
                        self.ship.resume(Ship.SHIP_ID_NOCHECK)

                tur.req.set_consume_listener(req_cont_len, callback)

            try:
                self.start_tour(tur)
                if tur.req.headers.content_length() <= 0:
                    self.end_req_content(Tour.TOUR_ID_NOCHECK, tur)

            except HttpException as e:
                BayLog.debug("%s Http error occurred: %s", self, e);
                if req_cont_len <= 0:
                    # no post data

                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)

                    return NextSocketAction.CONTINUE
                else:
                    # Delay send
                    tur.error = e
                    return NextSocketAction.CONTINUE

        return NextSocketAction.CONTINUE

    def handle_data(self, cmd):
        BayLog.debug("%s handle_data: stm=%d len=%d", self.ship, cmd.stream_id, cmd.length)

        tur = self.get_tour(cmd.stream_id)
        if tur is None:
            raise RuntimeError(f"Invalid stream id: {cmd.stream_id}")
        if tur.req.headers.content_length() <= 0:
            raise ProtocolException("Post content not allowed")

        success = False
        if cmd.length > 0:
            success = tur.req.post_content(Tour.TOUR_ID_NOCHECK, cmd.data, cmd.start, cmd.length)
            if tur.req.bytes_posted >= tur.req.headers.content_length():
                if tur.error:
                    # Error has occurred on header completed

                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, tur.error)
                    return NextSocketAction.CONTINUE
                else:
                    try:
                        self.end_req_content(tur.id(), tur)
                    except BaseException as e:
                        tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)
                        return NextSocketAction.CONTINUE

        if not success:
            return NextSocketAction.SUSPEND
        else:
            return NextSocketAction.CONTINUE

    def handle_priority(self, cmd):
        if cmd.stream_id == 0:
            raise ProtocolException("Invalid stream id")

        BayLog.debug("%s handlePriority: stmid=%d dep=%d, wgt=%d",
                     self.ship, cmd.stream_id, cmd.stream_dependency, cmd.weight);

        return NextSocketAction.CONTINUE

    def handle_settings(self, cmd):
        BayLog.debug("%s handleSettings: stmid=%d", self.ship, cmd.stream_id);

        if cmd.flags.ack():
            return NextSocketAction.CONTINUE

        for item in cmd.items:
            BayLog.debug("%s handle: Setting id=%d, value=%d", self.ship, item.id, item.value);

            if item.id == CmdSettings.HEADER_TABLE_SIZE:
                self.settings.header_table_size = item.value

            elif item.id == CmdSettings.ENABLE_PUSH:
                self.settings.enable_push = (item.value != 0)

            elif item.id == CmdSettings.MAX_CONCURRENT_STREAMS:
                self.settings.max_concurrent_streams = item.value

            elif item.id == CmdSettings.INITIAL_WINDOW_SIZE:
                self.settings.initial_window_size = item.value

            elif item.id == CmdSettings.MAX_FRAME_SIZE:
                self.settings.max_frame_size = item.value

            elif item.id == CmdSettings.MAX_HEADER_LIST_SIZE:
                self.settings.max_header_list_size = item.value

            else:
                BayLog.debug("Invalid settings id (Ignore): %d", item.id)

        res = CmdSettings(0, H2Flags(H2Flags.FLAGS_ACK))
        self.command_packer.post(self.ship, res)
        return NextSocketAction.CONTINUE

    def handle_window_update(self, cmd):
        BayLog.debug("%s handleWindowUpdate: stmid=%d siz=%d", self.ship, cmd.stream_id, cmd.window_size_increment);

        if cmd.window_size_increment == 0:
            raise ProtocolException("Invalid increment value")

        window_size = cmd.window_size_increment
        return NextSocketAction.CONTINUE

    def handle_go_away(self, cmd):
        BayLog.debug("%s received GoAway: lastStm=%d code=%d desc=%s debug=%s",
                     self.ship, cmd.last_stream_id, cmd.error_code, H2ErrorCode.msg.get(str(cmd.error_code)),
                     cmd.debug_data);
        return NextSocketAction.CLOSE

    def handle_ping(self, cmd):
        BayLog.debug("%s handle_ping: stm=%d", self.ship, cmd.stream_id)

        res = CmdPing(cmd.stream_id, H2Flags(H2Flags.FLAGS_ACK), cmd.opaque_data)
        self.command_packer.post(self.ship, res)
        return NextSocketAction.CONTINUE

    def handle_rst_stream(self, cmd):
        BayLog.debug("%s received RstStream: stmid=%d code=%d desc=%s",
                     self.ship, cmd.stream_id, cmd.error_code, H2ErrorCode.msg.get(str(cmd.error_code)))
        return NextSocketAction.CONTINUE


    #
    # private
    #
    def get_tour(self, key):
        return self.ship.get_tour(key)

    def end_req_content(self, check_id, tur):
        tur.req.end_content(check_id)

    def start_tour(self, tur):
        HttpUtil.parse_host_port(tur, 443 if self.ship.port_docker.secure else 80)
        HttpUtil.parse_authorization(tur)

        tur.req.protocol = self.http_protocol

        skt = self.ship.socket
        client_adr = tur.req.headers.get(Headers.X_FORWARDED_FOR)
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
            BayLog.error_e(e)
            BayLog.debug("%s Caught error (Continue)", self.ship)


        tur.req.server_port = tur.req.req_port
        tur.req.server_name = tur.req.req_host
        tur.is_secure = self.ship.port_docker.secure

        tur.go()

