import socket

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.http_exception import HttpException
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.tour.tour import Tour
from bayserver_core.tour.tour_req import TourReq
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.docker.base.inbound_handler import InboundHandler

from bayserver_core.util.simple_buffer import SimpleBuffer
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_util import HttpUtil
from bayserver_core.util.cgi_util import CgiUtil
from bayserver_core.util.class_util import ClassUtil

from bayserver_docker_fcgi.fcg_packet import FcgPacket
from bayserver_docker_fcgi.fcg_protocol_handler import FcgProtocolHandler
from bayserver_docker_fcgi.command.cmd_stdout import CmdStdOut
from bayserver_docker_fcgi.command.cmd_end_request import CmdEndRequest


class FcgInboundHandler(FcgProtocolHandler, InboundHandler):

    class InboundProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            return FcgInboundHandler(pkt_store)

    STATE_BEGIN_REQUEST = 1
    STATE_READ_PARAMS = 2
    STATE_READ_STDIN = 3

    def __init__(self, pkt_store):
        super().__init__(pkt_store, True)
        self.state = None
        self.cont_len = None
        self.req_id = None
        self.req_keep_alive = None
        self.env = {}
        self.reset_state()

    def __str__(self):
        return ClassUtil.get_local_name(self.__class__)


    ######################################################
    # implements Reusable
    ######################################################
    def reset(self):
        super().reset()
        self.env.clear()
        self.reset_state()

    ######################################################
    # implements InboundHandler
    ######################################################

    def send_res_headers(self, tur):
        BayLog.debug("%s PH:sendHeaders: tur=%s", self.ship, tur)

        scode = tur.res.headers.status
        status = f"{scode} {HttpStatus.description(scode)}"
        tur.res.headers.set(Headers.STATUS, status)

        if BayServer.harbor.trace_header:
            BayLog.info("%s resStatus:%d", tur, tur.res.headers.status)
            for name in tur.res.headers.names():
                for value in tur.res.headers.values(name):
                    BayLog.info("%s resHeader:%s=%s", tur, name, value)

        buf = SimpleBuffer()
        HttpUtil.send_mime_headers(tur.res.headers, buf)
        HttpUtil.send_new_line(buf)
        cmd = CmdStdOut(tur.req.key, buf.buf, 0, buf.length)
        self.command_packer.post(self.ship, cmd)

    def send_res_content(self, tur, bytes, ofs, length, callback):

        cmd = CmdStdOut(tur.req.key, bytes, ofs, length)
        self.command_packer.post(self.ship, cmd, callback)


    def send_end_tour(self, tur, keep_alive, cb):
        BayLog.debug("%s PH:endTour: tur=%s keep=%s", self.ship, tur, keep_alive)

        # Send empty stdout command
        cmd = CmdStdOut(tur.req.key)
        self.command_packer.post(self.ship, cmd)

        # Send end request command
        cmd = CmdEndRequest(tur.req.key)

        def ensure_func():
            if not keep_alive:
                self.command_packer.end(self.ship)

        def callback_func():
            BayLog.debug("%s call back in sendEndTour: tur=%s keep=%s", self, tur, keep_alive)
            ensure_func()
            cb()

        try:
            self.command_packer.post(self.ship, cmd, callback_func)
        except IOError as e:
            BayLog.debug("%s post failed in sendEndTour: tur=%s keep=%s", self, tur, keep_alive)
            ensure_func()
            raise e

    def send_req_protocol_error(self, err):
        tur = self.ship.get_error_tour()
        tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.BAD_REQUEST, err.message, err)
        return True


    ######################################################
    # implements FcgCommandHandler
    ######################################################
    def handle_begin_request(self, cmd):
        BayLog.debug("%s handle_begin_request req_id=%d} keep=%s", self.ship, cmd.req_id, cmd.keep_conn)

        if self.state != FcgInboundHandler.STATE_BEGIN_REQUEST:
            raise ProtocolException("Invalid FCGI command: %d state=%d", cmd.type, self.state)

        self.check_req_id(cmd.req_id)

        self.req_id = cmd.req_id
        BayLog.debug("%s begin_req get_tour req_id=%d", self.ship, cmd.req_id)
        tur = self.ship.get_tour(cmd.req_id)
        if tur is None:
            BayLog.error(BayMessage.get(Symbol.INT_NO_MORE_TOURS))
            tur = self.ship.get_tour(cmd.req_id, True)
            tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.SERVICE_UNAVAILABLE, "No available tours")
            self.ship.agent.shutdown(False)
            return NextSocketAction.CONTINUE

        self.req_keep_alive = cmd.keep_conn
        self.change_state(FcgInboundHandler.STATE_READ_PARAMS)
        return NextSocketAction.CONTINUE

    def handle_end_request(self, cmd):
        raise ProtocolException("Invalid FCGI command: %d", cmd.type)

    def handle_params(self, cmd):
        BayLog.debug("%s handle_params req_id=%d", self.ship, cmd.req_id)

        if self.state != FcgInboundHandler.STATE_READ_PARAMS:
            raise ProtocolException("Invalid FCGI command: %d state=%d", cmd.type, self.state)

        self.check_req_id(cmd.req_id)

        BayLog.debug("%s handle_param get_tour req_id=%d", self.ship, cmd.req_id)
        tur = self.ship.get_tour(cmd.req_id)

        if len(cmd.params) == 0:
            # Header completed

            # check keep-alive
            #  keep-alive flag of BeginRequest has high priority
            if self.req_keep_alive:
                if not tur.req.headers.contains(Headers.CONNECTION):
                    tur.req.headers.set(Headers.CONNECTION, "Keep-Alive")
                else:
                    tur.req.headers.set(Headers.CONNECTION, "Close")

            req_cont_len = tur.req.headers.content_length()

            BayLog.debug("%s read header method=%s protocol=%s uri=%s contlen=%d",
                         self.ship, tur.req.method, tur.req.protocol, tur.req.uri, self.cont_len)

            if BayServer.harbor.trace_header:
                for nv in cmd.params:
                    BayLog.info("%s  reqHeader: %s=%s", tur, nv[0], nv[1])

            if req_cont_len > 0:
                sid = self.ship.ship_id
                def callback(length, resume):
                    if resume:
                        self.ship.resume(sid)

                tur.req.set_consume_listener(req_cont_len, callback)

            self.change_state(FcgInboundHandler.STATE_READ_STDIN)
            try:
                self.start_tour(tur)
            except HttpException as e:
                BayLog.debug("%s Http error occurred: %s", self.ship, e)

                if req_cont_len <= 0:
                    # no post data
                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)
                    self.change_state(FcgInboundHandler.STATE_READ_STDIN)
                    return NextSocketAction.CONTINUE
                else:
                    # Delay send
                    self.change_state(FcgInboundHandler.STATE_READ_STDIN)
                    tur.error = e
                    tur.req.set_content_handler(ReqContentHandler.dev_null)
                    return NextSocketAction.CONTINUE

        else:
            if BayServer.harbor.trace_header:
                BayLog.info("%s Read FcgiParam", tur)

            for nv in cmd.params:
                name = nv[0]
                value = nv[1]
                if BayServer.harbor.trace_header:
                    BayLog.info("%s  param: %s=%s", tur, name, value);
                self.env[name] = value

                if name.startswith("HTTP_"):
                    hname = name[5:]
                    tur.req.headers.add(hname, value)
                elif name == "CONTENT_TYPE":
                    tur.req.headers.add(Headers.CONTENT_TYPE, value)
                elif name == "CONTENT_LENGTH":
                    tur.req.headers.add(Headers.CONTENT_LENGTH, value)
                elif name == "HTTPS":
                    tur.is_secure = value.lower() == "on"

            tur.req.uri = self.env["REQUEST_URI"]
            tur.req.protocol = self.env["SERVER_PROTOCOL"]
            tur.req.method = self.env["REQUEST_METHOD"]

            return NextSocketAction.CONTINUE

    def handle_stderr(self, cmd):
        raise ProtocolException("Invalid FCGI command: %d", cmd.type)

    def handle_stdin(self, cmd):
        BayLog.debug("%s handle_stdin req_id=%d len=%d", self.ship, cmd.req_id, cmd.length)

        if self.state != FcgInboundHandler.STATE_READ_STDIN:
            raise ProtocolException("Invalid FCGI command: %d state=%d", cmd.type, self.state)


        self.check_req_id(cmd.req_id)

        tur = self.ship.get_tour(cmd.req_id)
        if cmd.length == 0:
            #  request content completed
            if tur.error:
                # Error has occurred on header completed
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, tur.error)
                self.reset_state()
                return NextSocketAction.WRITE
            else:
                try:
                    self.end_req_content(Tour.TOUR_ID_NOCHECK, tur)
                    return NextSocketAction.CONTINUE
                except HttpException as e:
                    tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)
                    return NextSocketAction.WRITE

        else:
            success = tur.req.post_content(Tour.TOUR_ID_NOCHECK, cmd.data, cmd.start, cmd.length)

            if not success:
                return NextSocketAction.SUSPEND
            else:
                return NextSocketAction.CONTINUE

    def handle_stdout(self, cmd):
        raise ProtocolException("Invalid FCGI command: %d", cmd.type)

    #
    # private
    #
    def check_req_id(self, received_id):
        if received_id == FcgPacket.FCGI_NULL_REQUEST_ID:
            raise ProtocolException("Invalid request id: %d", received_id)

        if self.req_id == FcgPacket.FCGI_NULL_REQUEST_ID:
            self.req_id = received_id

        if self.req_id != received_id:
            BayLog.error("%s invalid request id: received=%d reqId=%d", self.ship(), received_id, self.req_id)
            raise ProtocolException("Invalid request id: %d", received_id)

    def change_state(self, new_state):
        self.state = new_state

    def reset_state(self):
        self.change_state(FcgInboundHandler.STATE_BEGIN_REQUEST)
        self.req_id = FcgPacket.FCGI_NULL_REQUEST_ID
        self.cont_len = 0

    def end_req_content(self, check_id, tur):
        tur.req.end_content(check_id)
        self.reset_state()

    def start_tour(self, tur):
        HttpUtil.parse_host_port(tur, 443 if tur.is_secure else 80)
        HttpUtil.parse_authorization(tur)

        tur.req.remote_port = int(self.env[CgiUtil.REMOTE_PORT])
        tur.req.remote_address = self.env[CgiUtil.REMOTE_ADDR]
        tur.req.remote_host_func = lambda: HttpUtil.resolve_remote_host(tur.req.remote_address)

        tur.req.server_name = self.env[CgiUtil.SERVER_NAME]
        tur.req.server_address = self.env[CgiUtil.SERVER_ADDR]
        tur.req.server_port = int(self.env[CgiUtil.SERVER_PORT])

        tur.go()

