from typing import List

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.common.warp_ship import WarpShip
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.sink import Sink
from bayserver_core.tour.tour import Tour
from bayserver_core.common.warp_data import WarpData
from bayserver_core.common.warp_handler import WarpHandler
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_docker_ajp.ajp_command_unpacker import AjpCommandUnPacker
from bayserver_docker_ajp.ajp_handler import AjpHandler
from bayserver_docker_ajp.ajp_packet_unpacker import AjpPacketUnPacker
from bayserver_docker_ajp.ajp_protocol_handler import AjpProtocolHandler
from bayserver_docker_ajp.command.cmd_forward_request import CmdForwardRequest
from bayserver_docker_ajp.command.cmd_data import CmdData


class AjpWarpHandler(AjpHandler, WarpHandler):
    class WarpProtocolHandlerFactory:

        def create_protocol_handler(self, pkt_store):
            ib_handler = AjpWarpHandler()
            cmd_unpacker = AjpCommandUnPacker(ib_handler)
            pkt_unpacker = AjpPacketUnPacker(pkt_store, cmd_unpacker)
            pkt_packer = PacketPacker()
            cmd_packer = CommandPacker(pkt_packer, pkt_store)

            proto_handler = AjpProtocolHandler(ib_handler, pkt_unpacker, pkt_packer, cmd_unpacker, cmd_packer, False)
            ib_handler.init(proto_handler)
            return proto_handler

    FIXED_WARP_ID = 1

    STATE_READ_HEADER = 1
    STATE_READ_CONTENT = 2

    protocol_handler: AjpProtocolHandler
    state: int
    req_read_len: int

    def __init__(self):
        self.state = None
        self.cont_read_len = None
        self.protocol_handler = None
        self.reset()

    def init(self, protocol_handler: AjpProtocolHandler):
        self.protocol_handler = protocol_handler

    def reset(self):
        super().reset()
        self.reset_state()
        self.cont_read_len = 0

    def ship(self) -> WarpShip:
        return self.protocol_handler.ship

    def __str__(self):
        return str(self.ship())


    ######################################################
    # Implements WarpHandler
    ######################################################
    def next_warp_id(self):
        return 1

    def new_warp_data(self, warp_id):
        return WarpData(self.ship(), warp_id)

    def send_req_headers(self, tur):
        self.send_forward_request(tur)

    def send_req_contents(self, tur: Tour, buf: bytearray, start: int, length: int, lis: DataConsumeListener):
        self.send_data(tur, buf, start, length, lis)

    def send_end_req(self, tur: Tour, keep_alive: bool, lis: DataConsumeListener):
        self.ship().post(None, lis)

    def verify_protocol(self, proto):
        pass

    def on_protocol_error(self, err: ProtocolException, stk: List[str]) -> bool:
        raise Sink()

    ######################################################
    # Implements AjpCommandHandler
    ######################################################
    def handle_data(self, cmd):
        raise ProtocolException("Invalid AJP command: %d", cmd.type)

    def handle_end_response(self, cmd):
        BayLog.debug("%s handle_end_response reuse=%s", self.ship, cmd.reuse)
        tur = self.ship().get_tour(AjpWarpHandler.FIXED_WARP_ID)

        if self.state == AjpWarpHandler.STATE_READ_HEADER:
            self.end_res_header(tur)

        self.end_res_content(tur, cmd.reuse)
        if cmd.reuse:
            return NextSocketAction.CONTINUE
        else:
            return NextSocketAction.CLOSE

    def handle_forward_request(self, cmd):
        raise ProtocolException("Invalid AJP command: %s", cmd.type)

    def handle_send_body_chunk(self, cmd):
        BayLog.debug("%s handle_send_body_chunk len=%d", self.ship, cmd.length)
        tur = self.ship().get_tour(AjpWarpHandler.FIXED_WARP_ID)

        if self.state == AjpWarpHandler.STATE_READ_HEADER:

            sid = self.ship().ship_id

            def callback(length, resume):
                if resume:
                    self.ship().resume_read(sid)

            tur.res.set_res_consume_listener(callback)

            self.end_res_header(tur)

        available = tur.res.send_res_content(tur.tour_id, cmd.chunk, 0, cmd.length)
        self.cont_read_len += cmd.length

        if available:
            return NextSocketAction.CONTINUE
        else:
            return NextSocketAction.SUSPEND

    def handle_send_headers(self, cmd):
        BayLog.debug("%s handle_send_headers", self.ship)

        tur = self.ship().get_tour(AjpWarpHandler.FIXED_WARP_ID)

        if self.state != AjpWarpHandler.STATE_READ_HEADER:
            raise ProtocolException("Invalid AJP command: %d state=%s", cmd.type, self.state)

        wdat = WarpData.get(tur)

        if BayServer.harbor.trace_header():
            BayLog.info("%s recv res status: %d", wdat, cmd.status)

        wdat.res_headers.status = cmd.status
        for name in cmd.headers.keys():
            for value in cmd.headers[name]:
                if BayServer.harbor.trace_header():
                    BayLog.info("%s recv res header: %s=%s", wdat, name, value)

                wdat.res_headers.add(name, value)


        return NextSocketAction.CONTINUE

    def handle_shutdown(self, cmd):
        raise ProtocolException("Invalid AJP command: %d", cmd.type)

    def handle_get_body_chunk(self, cmd):
        BayLog.debug("%s handle_get_body_chunk", self)
        return NextSocketAction.CONTINUE

    def handle_eof(self):
        raise EOFError()

    def need_data(self):
        return False

    #
    # private
    #
    def end_res_header(self, tur: Tour):
        wdat = WarpData.get(tur)
        wdat.res_headers.copy_to(tur.res.headers)
        tur.res.send_res_headers(Tour.TOUR_ID_NOCHECK)
        self.change_state(AjpWarpHandler.STATE_READ_CONTENT)

    def end_res_content(self, tur: Tour, keep: bool):
        self.ship().end_warp_tour(tur, keep)
        tur.res.end_res_content(Tour.TOUR_ID_NOCHECK)
        self.reset_state()

    def change_state(self, new_state: int):
        self.state = new_state

    def reset_state(self):
        self.change_state(AjpWarpHandler.STATE_READ_HEADER)

    def send_forward_request(self, tur: Tour):
        BayLog.debug("%s construct header", tur)

        cmd = CmdForwardRequest()
        cmd.to_server = True
        cmd.method = tur.req.method
        cmd.protocol = tur.req.protocol
        if tur.req.rewritten_uri:
            rel_uri = tur.req.rewritten_uri
        else:
            rel_uri = tur.req.uri
        town_path = tur.town.name
        if not town_path.endswith("/"):
            town_path += "/"

        rel_uri = rel_uri[len(town_path):]
        req_uri = self.ship().docker.warp_base() + rel_uri

        pos = req_uri.find('?')
        if pos > 0:
            cmd.req_uri = req_uri[0:pos]
            cmd.attributes["?query_string"] = req_uri[pos + 1:]
        else:
            cmd.req_uri = req_uri

        cmd.remote_addr = tur.req.remote_address
        cmd.remote_host = tur.req.remote_host()
        cmd.server_name = tur.req.server_name
        cmd.server_port = self.ship().docker.port()
        cmd.is_ssl = tur.is_secure
        cmd.headers = tur.req.headers

        if BayServer.harbor.trace_header():
            for name in cmd.headers.names():
                for value in cmd.headers.values(name):
                    BayLog.info("%s sendWarpHeader: %s=%s", WarpData.get(tur), name, value)

        self.ship().post(cmd)

    def send_data(self, tur: Tour, data: bytearray, ofs: int, length: int, lis: DataConsumeListener):
        BayLog.debug("%s construct contents", tur)

        cmd = CmdData(data, ofs, length)
        cmd.to_server = True

        self.ship().post(cmd, lis)
