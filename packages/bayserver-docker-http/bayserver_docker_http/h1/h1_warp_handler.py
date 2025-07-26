
from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.common.warp_ship import WarpShip
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.sink import Sink

from bayserver_core.tour.tour import Tour
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.common.warp_data import WarpData
from bayserver_core.common.warp_handler import WarpHandler
from bayserver_docker_http.h1.h1_command_unpacker import H1CommandUnPacker
from bayserver_docker_http.h1.h1_handler import H1Handler
from bayserver_docker_http.h1.h1_packet_unpacker import H1PacketUnPacker

from bayserver_docker_http.h1.h1_protocol_handler import H1ProtocolHandler
from bayserver_docker_http.h1.command.cmd_header import CmdHeader
from bayserver_docker_http.h1.command.cmd_content import CmdContent
from bayserver_docker_http.h1.command.cmd_end_content import CmdEndContent

class H1WarpHandler(H1Handler, WarpHandler):
    class WarpProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            ib_handler = H1WarpHandler()
            cmd_unpacker = H1CommandUnPacker(ib_handler, False)
            pkt_unpacker = H1PacketUnPacker(cmd_unpacker, pkt_store)
            pkt_packer = PacketPacker()
            cmd_packer = CommandPacker(pkt_packer, pkt_store)

            proto_handler = H1ProtocolHandler(ib_handler, pkt_unpacker, pkt_packer, cmd_unpacker, cmd_packer, True)
            ib_handler.init(proto_handler)
            return proto_handler

    STATE_READ_HEADER = 1
    STATE_READ_CONTENT = 2
    STATE_FINISHED = 3

    FIXED_WARP_ID = 1

    protocol_handler: H1ProtocolHandler = None
    state: int

    def __init__(self):
        self.state = None
        self.reset()

    def init(self, ph: H1ProtocolHandler):
        self.protocol_handler = ph

    def ship(self) -> WarpShip:
        return self.protocol_handler.ship


    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        super().reset()
        self.change_state(H1WarpHandler.STATE_FINISHED)


    ######################################################
    # Implements WarpHandler
    ######################################################
    def next_warp_id(self):
        return H1WarpHandler.FIXED_WARP_ID

    def new_warp_data(self, warp_id):
        return WarpData(self.ship(), warp_id)

    def send_req_headers(self, tur: Tour):
        twn = tur.town

        twn_path = twn.name
        if not twn_path.endswith("/"):
            twn_path += "/"

        sip = self.ship()
        new_uri = sip.docker.warp_base() + tur.req.uri[len(twn_path):]
        cmd = CmdHeader.new_req_header(tur.req.method, new_uri, "HTTP/1.1")

        for name in tur.req.headers.names():
            for value in tur.req.headers.values(name):
                cmd.add_header(name, value)


        if tur.req.headers.contains(Headers.X_FORWARDED_FOR):
            cmd.set_header(Headers.X_FORWARDED_FOR, tur.req.headers.get(Headers.X_FORWARDED_FOR))
        else:
            cmd.set_header(Headers.X_FORWARDED_FOR, tur.req.remote_address)

        if tur.req.headers.contains(Headers.X_FORWARDED_PROTO):
            cmd.set_header(Headers.X_FORWARDED_PROTO, tur.req.headers.get(Headers.X_FORWARDED_PROTO))
        else:
            cmd.set_header(Headers.X_FORWARDED_PROTO, "https" if tur.is_secure else "http")


        if tur.req.headers.contains(Headers.X_FORWARDED_PORT):
            cmd.set_header(Headers.X_FORWARDED_PORT, tur.req.headers.get(Headers.X_FORWARDED_PORT))
        else:
            cmd.set_header(Headers.X_FORWARDED_PORT, str(tur.req.server_port))

        if tur.req.headers.contains(Headers.X_FORWARDED_HOST):
            cmd.set_header(Headers.X_FORWARDED_HOST, tur.req.headers.get(Headers.X_FORWARDED_HOST))
        else:
            cmd.set_header(Headers.X_FORWARDED_HOST, tur.req.headers.get(Headers.HOST))

        cmd.set_header(Headers.HOST, f"{sip.docker._host}:{sip.docker._port}")
        cmd.set_header(Headers.CONNECTION, "Keep-Alive")

        if BayServer.harbor.trace_header():
            for kv in cmd.headers:
                BayLog.info("%s warp_http reqHdr: %s=%s", tur, kv[0], kv[1])

        self.ship().post(cmd)

    def send_req_contents(self, tur: Tour, buf: bytearray, start: int, length: int, lis: DataConsumeListener):
        cmd = CmdContent(buf, start, length)
        self.ship().post(cmd, lis)


    def send_end_req(self, tur: Tour, keep_alive: bool, lis: DataConsumeListener):
        cmd = CmdEndContent()
        self.ship().post(cmd, lis)


    def verify_protocol(self, proto):
        pass


    ######################################################
    # Implements H1CommandHandler
    ######################################################

    def handle_header(self, cmd):
        tur = self.ship().get_tour(H1WarpHandler.FIXED_WARP_ID)
        wdat = WarpData.get(tur)
        BayLog.debug("%s handleHeader status=%d", wdat, cmd.status);
        self.ship().keeping = False

        if self.state == H1WarpHandler.STATE_FINISHED:
            self.change_state(H1WarpHandler.STATE_READ_HEADER)

        if self.state != H1WarpHandler.STATE_READ_HEADER:
            raise ProtocolException("Header command not expected: state=%d", self.state)

        if BayServer.harbor.trace_header():
            BayLog.info("%s warp_http: resStatus: %d", wdat, cmd.status)

        for nv in cmd.headers:
            tur.res.headers.add(nv[0], nv[1])
            if BayServer.harbor.trace_header():
                BayLog.info("%s warp_http: resHeader: %s=%s", wdat, nv[0], nv[1]);

        tur.res.headers.status = cmd.status
        res_cont_len = tur.res.headers.content_length()
        tur.res.send_res_headers(Tour.TOUR_ID_NOCHECK)

        if res_cont_len == 0 or cmd.status == HttpStatus.NOT_MODIFIED:
            self.end_res_content(tur)
        else:
            self.change_state(H1WarpHandler.STATE_READ_CONTENT)
            sid = self.ship().id()

            def callback(length: int, resume: bool):
                if resume:
                    self.ship().resume_read(sid)

            tur.res.set_res_consume_listener(callback)

        return NextSocketAction.CONTINUE

    def handle_content(self, cmd):
        tur = self.ship().get_tour(H1WarpHandler.FIXED_WARP_ID)
        wdat = WarpData.get(tur)
        BayLog.debug("%s handleContent len=%d posted=%d contLen=%d", wdat, cmd.length, tur.res.bytes_posted,
                     tur.res.bytes_limit);

        if self.state != H1WarpHandler.STATE_READ_CONTENT:
            raise ProtocolException("Content command not expected")

        available = tur.res.send_res_content(tur.tour_id, cmd.buf, cmd.start, cmd.length)
        if tur.res.bytes_posted == tur.res.bytes_limit:
            self.end_res_content(tur)
            return NextSocketAction.CONTINUE
        elif not available:
            return NextSocketAction.SUSPEND

        else:
            return NextSocketAction.CONTINUE

    def handle_end_content(self, cmd):
        raise Sink()


    def on_protocol_error(self, e: ProtocolException) -> bool:
        raise Sink()

    def req_finished(self):
        return self.state == H1WarpHandler.STATE_FINISHED


    #
    # private
    #
    def end_res_content(self, tur: Tour):
        BayLog.debug("%s endResContent tur=%s", self, tur)
        self.ship().end_warp_tour(tur, True)
        tur.res.end_res_content(tur.tour_id)
        self.reset()
        self.ship().keeping = True

    def change_state(self, new_state: int):
        self.state = new_state


