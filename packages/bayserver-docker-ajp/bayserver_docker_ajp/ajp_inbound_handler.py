from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.http_exception import HttpException

from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.tour.tour import Tour
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.docker.base.inbound_handler import InboundHandler
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.http_util import HttpUtil
from bayserver_docker_ajp.ajp_packet import AjpPacket
from bayserver_docker_ajp.ajp_protocol_handler import AjpProtocolHandler
from bayserver_docker_ajp.command.cmd_get_body_chunk import CmdGetBodyChunk
from bayserver_docker_ajp.command.cmd_send_headers import CmdSendHeaders
from bayserver_docker_ajp.command.cmd_end_response import CmdEndResponse
from bayserver_docker_ajp.command.cmd_send_body_chunk import CmdSendBodyChunk



class AjpInboundHandler(AjpProtocolHandler, InboundHandler):
    class InboundProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            return AjpInboundHandler(pkt_store)

    STATE_READ_FORWARD_REQUEST = 1
    STATE_READ_DATA = 2

    DUMMY_KEY = 1

    def __init__(self, pkt_store):
        super().__init__(pkt_store, True)
        self.cur_tour_id = None
        self.req_command = None

        self.state = None
        self.keeping = None
        self.reset_state()


    ######################################################
    # implements Reusable
    ######################################################
    def reset(self):
        super().reset()
        self.reset_state()
        self.req_command = None
        self.keeping = False
        self.cur_tour_id = 0

    ######################################################
    # implements InboundHandler
    ######################################################

    def send_res_headers(self, tur):
        chunked = False
        cmd = CmdSendHeaders()
        for name in tur.res.headers.names():
            for value in tur.res.headers.values(name):
                cmd.add_header(name, value)

        cmd.status = tur.res.headers.status
        self.command_packer.post(self.ship, cmd)

        BayLog.debug("%s send header: content-length=%d", self, tur.res.headers.content_length())

    def send_res_content(self, tur, bytes, ofs, length, callback):
        cmd = CmdSendBodyChunk(bytes, ofs, length);
        self.command_packer.post(self.ship, cmd, callback)

    def send_end_tour(self, tur, keep_alive, cb):
        BayLog.debug("%s endTour: tur=%s keep=%s", self.ship, tur, keep_alive)
        cmd = CmdEndResponse()
        cmd.reuse = keep_alive

        def ensure_func():
            if not keep_alive:
                self.command_packer.end(self.ship)

        def callback_func():
            BayLog.debug("%s call back in sendEndTour: tur=%s keep=%s", self, tur, keep_alive)
            ensure_func()
            cb()

        try:
            self.command_packer.post(self.ship, cmd, callback_func())
        except IOError as e:
            BayLog.debug("%s post failed in sendEndTour: tur=%s keep=%s", self, tur, keep_alive)
            ensure_func()
            raise e

    def send_req_protocol_error(self, e):
        tur = self.ship.get_error_tour()
        tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.BAD_REQUEST, e.message, e)
        return True



    ######################################################
    # implements AjpCommandHandler
    ######################################################
    def handle_forward_request(self, cmd):
        BayLog.debug("%s handleForwardRequest method=%s uri=%s", self.ship, cmd.method, cmd.req_uri)
        if self.state != AjpInboundHandler.STATE_READ_FORWARD_REQUEST:
            raise ProtocolException("Invalid AJP command: #{cmd.type}")

        self.keeping = False
        self.req_command = cmd
        tur = self.ship.get_tour(AjpInboundHandler.DUMMY_KEY)
        if tur is None:
            BayLog.error(BayMessage.get(Symbol.INT_NO_MORE_TOURS))
            tur = self.ship.get_tour(AjpInboundHandler.DUMMY_KEY, True)
            tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.SERVICE_UNAVAILABLE, "No available tours")
            tur.res.end_content(Tour.TOUR_ID_NOCHECK)
            self.ship.agent.shutdown(False)
            return NextSocketAction.CONTINUE

        self.cur_tour_id = tur.id
        tur.req.uri = cmd.req_uri
        tur.req.protocol = cmd.protocol
        tur.req.method = cmd.method
        cmd.headers.copy_to(tur.req.headers)
        query_string = cmd.attributes.get("?query_string")

        if StringUtil.is_set(query_string):
            tur.req.uri += "?" + query_string

        BayLog.debug("%s read header method=%s protocol=%s uri=%s contlen=%d",
                     tur, tur.req.method, tur.req.protocol, tur.req.uri, tur.req.headers.content_length())

        if BayServer.harbor.trace_header:
            for name in cmd.headers.names():
                for value in cmd.headers.values(name):
                    BayLog.info("%s header: %s=%s", tur, name, value)

        req_cont_len = cmd.headers.content_length()
        if req_cont_len > 0:
            sid = self.ship.ship_id
            def callback(le, resume):
                if resume:
                    self.ship.resume(sid)

            tur.req.set_consume_listener(req_cont_len, callback)

        try:
            self.start_tour(tur)

            if req_cont_len <= 0:
                self.end_req_content(tur)
            else:
                self.change_state(AjpInboundHandler.STATE_READ_DATA)

            return NextSocketAction.CONTINUE

        except HttpException as e:

            if req_cont_len <= 0:
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)
                self.reset_state()
                return NextSocketAction.WRITE
            else:
                # Delay send
                self.change_state(AjpInboundHandler.STATE_READ_DATA)
                tur.error = e
                tur.req.set_content_handler(ReqContentHandler.dev_null)
                return NextSocketAction.CONTINUE

    def handle_data(self, cmd):
        BayLog.debug("%s handleData len=%s", self.ship, cmd.length)

        if self.state != AjpInboundHandler.STATE_READ_DATA:
            raise RuntimeError(f"Invalid AJP command: {cmd.type} state={self.state}")

        tur = self.ship.get_tour(AjpInboundHandler.DUMMY_KEY)
        success = tur.req.post_content(Tour.TOUR_ID_NOCHECK, cmd.data, cmd.start, cmd.length)

        if tur.req.bytes_posted == tur.req.bytes_limit:
            # request content completed

            if tur.error is not None:
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, tur.error)
                self.reset_state()
                return NextSocketAction.WRITE
            else:
                try:
                    self.end_req_content(tur)
                    return NextSocketAction.CONTINUE
                except HttpException as e:
                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)
                    self.reset_state()
                return NextSocketAction.WRITE

        else:
            bch = CmdGetBodyChunk()
            bch.req_len = tur.req.bytes_limit - tur.req.bytes_posted
            if bch.req_len > AjpPacket.MAX_DATA_LEN:
                bch.req_len = AjpPacket.MAX_DATA_LEN

            self.command_packer.post(self.ship, bch)

            if not success:
                return NextSocketAction.SUSPEND
            else:
                return NextSocketAction.CONTINUE

    def handle_send_body_chunk(self, cmd):
        raise RuntimeError(f"Invalid AJP command: {cmd.type}")

    def handle_send_headers(self, cmd):
        raise RuntimeError(f"Invalid AJP command: {cmd.type}")

    def handle_shutdown(self, cmd):
        BayLog.info("%s handle_shutdown", self.ship)
        BayServer.shutdown()
        return NextSocketAction.CLOSE

    def handle_end_response(self, cmd):
        raise RuntimeError(f"Invalid AJP command: {cmd.type}")

    def handle_get_body_chunk(self, cmd):
        raise RuntimeError("Invalid AJP command: {cmd.type}")

    def need_data(self):
        return self.state == AjpInboundHandler.STATE_READ_DATA

    #
    # private
    #

    def reset_state(self):
        self.change_state(AjpInboundHandler.STATE_READ_FORWARD_REQUEST)

    def change_state(self, new_state):
        self.state = new_state

    def end_req_content(self, tur):
        tur.req.end_content(Tour.TOUR_ID_NOCHECK)
        self.reset_state()

    def start_tour(self, tur):
        HttpUtil.parse_host_port(tur, 443 if self.req_command.is_ssl else 80)
        HttpUtil.parse_authorization(tur)

        skt = self.ship.socket

        tur.req.remote_port = None
        tur.req.remote_address = self.req_command.remote_addr

        tur.req.remote_host_func = lambda: self.req_command.remote_host

        server_addr = skt.getsockname()
        tur.req.server_address = server_addr[0]

        tur.req.server_port = self.req_command.server_port
        tur.req.server_name = self.req_command.server_name
        tur.is_secure = self.req_command.is_ssl

        tur.go()