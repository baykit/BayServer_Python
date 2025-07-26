import threading
from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.bay_message import BayMessage
from bayserver_core.common.inbound_ship import InboundShip
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.symbol import Symbol
from bayserver_core.sink import Sink

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.upgrade_exception import UpgradeException
from bayserver_core.http_exception import HttpException
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.common.inbound_handler import InboundHandler

from bayserver_core.tour.tour import Tour
from bayserver_core.util.class_util import ClassUtil
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.http_util import HttpUtil
from bayserver_core.util.url_encoder import URLEncoder
from bayserver_core.util.headers import Headers
from bayserver_core.util.exception_util import ExceptionUtil
from bayserver_docker_http.h1.h1_command_unpacker import H1CommandUnPacker
from bayserver_docker_http.h1.h1_handler import H1Handler
from bayserver_docker_http.h1.h1_packet_unpacker import H1PacketUnPacker

from bayserver_docker_http.h1.h1_protocol_handler import H1ProtocolHandler
from bayserver_docker_http.htp_docker import HtpDocker
from bayserver_docker_http.h1.command.cmd_header import CmdHeader
from bayserver_docker_http.h1.command.cmd_content import CmdContent
from bayserver_docker_http.h1.command.cmd_end_content import CmdEndContent


class H1InboundHandler(H1Handler, InboundHandler):

    class InboundProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            ib_handler = H1InboundHandler()
            cmd_unpacker = H1CommandUnPacker(ib_handler, True)
            pkt_unpacker = H1PacketUnPacker(cmd_unpacker, pkt_store)
            pkt_packer = PacketPacker()
            cmd_packer = CommandPacker(pkt_packer, pkt_store)

            proto_handler = H1ProtocolHandler(ib_handler, pkt_unpacker, pkt_packer, cmd_unpacker, cmd_packer, True)
            ib_handler.init(proto_handler)
            return proto_handler

    STATE_READ_HEADER = 1
    STATE_READ_CONTENT = 2
    STATE_FINISHED = 3

    FIXED_REQ_ID = 1

    protocol_handler: H1ProtocolHandler
    header_read: bool
    http_protocol: str

    state: int
    cur_req_id: int
    cur_tour: Tour
    cur_tour_id: int

    def __init__(self):
        self.reset()

    def __str__(self):
        return ClassUtil.get_local_name(self.__class__)

    def init(self, protocol_handler: H1ProtocolHandler) -> None:
        self.protocol_handler = protocol_handler



    ######################################################
    # implements Reusable
    ######################################################
    def reset(self):
        super().reset()
        self.cur_req_id = 1
        self.reset_state()

        self.header_read = False
        self.http_protocol = None
        self.cur_req_id = 1
        self.cur_tour = None
        self.cur_tour_id = 0

    ######################################################
    # implements InboundHandler
    ######################################################
    def send_res_headers(self, tur):

        # determine Connection header value
        if tur.req.headers.get_connection() != Headers.CONNECTION_KEEP_ALIVE:
            # If client doesn't support "Keep-Alive", set "Close"
            res_con = "Close"
        else:
            res_con = "Keep-Alive"
            # Client supports "Keep-Alive"
            if tur.res.headers.get_connection() != Headers.CONNECTION_KEEP_ALIVE:
                # If tours doesn't need "Keep-Alive"
                if tur.res.headers.content_length() == -1:
                    # If content-length not specified
                    if (tur.res.headers.content_type() is not None and
                            tur.res.headers.content_type().startswith("text/")):
                        # If content is text, connection must be closed
                        res_con = "Close"

        tur.res.headers.set(Headers.CONNECTION, res_con)

        if BayServer.harbor.trace_header():
            BayLog.info("%s resStatus:%d", tur, tur.res.headers.status)
            for name in tur.res.headers.names():
                for value in tur.res.headers.values(name):
                    BayLog.info("%s resHeader:%s=%s", tur, name, value)

        cmd = CmdHeader.new_res_header(tur.res.headers, tur.req.protocol)
        self.protocol_handler.post(cmd)

    def send_res_content(self, tur, bytes, ofs, length, callback):
        BayLog.debug("%s H1 send_res_content len=%d", self, length)
        cmd = CmdContent(bytes, ofs, length)
        self.protocol_handler.post(cmd, callback)

    def send_end_tour(self, tur, keep_alive, cb):
        BayLog.debug("%s %s sendEndTour: tur=%s keep=%s", threading.current_thread().name, self.ship, tur, keep_alive)

        sid = self.ship().ship_id
        def ensure_func():
            if keep_alive:
                self.ship().keeping = True
                self.ship().resume_read(sid)
            else:
                self.ship().post_close()

        def callback_func():
            BayLog.debug("%s call back of end content command: tur=%s", self.ship, tur)
            ensure_func()
            cb()

        # Send dummy end request command
        cmd = CmdEndContent()
        try:
            self.protocol_handler.post(cmd, callback_func)
        except IOError as e:
            ensure_func()
            raise e

    def send_req_protocol_error(self, err):
        if self.cur_tour is None:
            tur = self.ship().get_error_tour()
        else:
            tur = self.cur_tour

        tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.BAD_REQUEST, ExceptionUtil.message(err), err)
        return True


    def on_protocol_error(self, e: Exception) -> bool:
        BayLog.debug("%s onProtocolError: %s", self.ship(), e)
        if self.cur_tour is None:
            tur = self.ship().get_error_tour()
        else:
            tur = self.cur_tour

        tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.BAD_REQUEST, ExceptionUtil.message(e))
        return True

    ######################################################
    # implements H1CommandHandler
    ######################################################
    def handle_header(self, cmd):
        sip = self.ship()
        BayLog.debug("%s handleHeader: method=%s uri=%s proto=%s", sip, cmd.method, cmd.uri, cmd.version);

        if self.state == H1InboundHandler.STATE_FINISHED:
            self.change_state(H1InboundHandler.STATE_READ_HEADER)

        if self.state != H1InboundHandler.STATE_READ_HEADER or self.cur_tour is not None:
            msg = f"Header command not expected: state=#{self.state} curTur=#{self.cur_tour}"
            self.reset_state()
            raise ProtocolException(msg)

        # Check HTTP2
        protocol = cmd.version.upper()
        if protocol == "HTTP/2.0":
            if sip.port_docker.support_h2:
                sip.port_docker.return_protocol_handler(sip.agent_id, self.protocol_handler)
                new_hnd = ProtocolHandlerStore.get_store(HtpDocker.H2_PROTO_NAME, True, sip.agent_id).rent()
                sip.set_protocol_handler(new_hnd)
                raise UpgradeException()
            else:
                raise ProtocolException(BayMessage.get(Symbol.HTP_UNSUPPORTED_PROTOCOL, protocol))

        tur = sip.get_tour(self.cur_req_id)
        if tur is None:
            BayLog.error(BayMessage.get(Symbol.INT_NO_MORE_TOURS))
            tur = sip.get_tour(self.cur_req_id, True)
            tur.res.send_error(Tour.TOUR_ID_NOCHECK, HttpStatus.SERVICE_UNAVAILABLE, "No available tours")
            return NextSocketAction.CONTINUE

        self.cur_tour = tur
        self.cur_tour_id = tur.tour_id
        self.cur_req_id += 1

        sip.keeping = False

        self.http_protocol = protocol

        tur.req.uri = URLEncoder.encode_tilde(cmd.uri)
        tur.req.method = cmd.method.upper()
        tur.req.protocol = protocol

        if not (tur.req.protocol == "HTTP/1.1" or
                tur.req.protocol == "HTTP/1.0" or
                tur.req.protocol == "HTTP/0.9"):

            raise ProtocolException(BayMessage.get(Symbol.HTP_UNSUPPORTED_PROTOCOL, tur.req.protocol))

        for nv in cmd.headers:
            tur.req.headers.add(nv[0], nv[1])

        req_cont_len = tur.req.headers.content_length()
        BayLog.debug("%s read header method=%s protocol=%s uri=%s contlen=%d",
                     self.ship, tur.req.method, tur.req.protocol, tur.req.uri, tur.req.headers.content_length())

        if BayServer.harbor.trace_header():
            for item in cmd.headers:
                BayLog.info("%s h1: reqHeader: %s=%s", tur, item[0], item[1])

        if req_cont_len > 0:
            tur.req.set_limit(req_cont_len)

        try:
            self.start_tour(tur)

            if req_cont_len <= 0:
                self.end_req_content(self.cur_tour_id, tur)
                return NextSocketAction.SUSPEND  # end reading
            else:
                self.change_state(H1InboundHandler.STATE_READ_CONTENT)
                return NextSocketAction.CONTINUE

        except HttpException as e:
            BayLog.debug_e(e, "%s Http error occurred: %s", self, e)
            if req_cont_len <= 0:
                # no post data
                tur.res.send_http_exception(Tour.TOUR_ID_NOCHECK, e)

                self.reset_state()  # next: read empty stdin command
                return NextSocketAction.CONTINUE
            else:
                # Delay send
                BayLog.trace("%s error sending is delayed", self)
                self.change_state(H1InboundHandler.STATE_READ_CONTENT)
                tur.error = e
                return NextSocketAction.CONTINUE

    def handle_content(self, cmd):
        BayLog.debug("%s handleContent: len=%s", self.ship, cmd.  length)

        if self.state != H1InboundHandler.STATE_READ_CONTENT:
            s = self.state
            self.reset_state()
            raise ProtocolException(f"Content command not expected: state=#{s}")

        tur = self.cur_tour
        tur_id = self.cur_tour_id

        try:
            sid = self.ship().ship_id
            def callback(length: int, resume: bool):
                if resume:
                    self.ship().resume_read(sid)

            success = tur.req.post_req_content(tur_id, cmd.buf, cmd.start, cmd.length, callback)

            if tur.req.bytes_posted == tur.req.bytes_limit:
                if tur.error:
                    # Error has occurred on header completed
                    tur.res.send_http_exception(tur_id, tur.error)
                    raise tur.error
                else:
                    self.end_req_content(tur_id, tur)
                    return NextSocketAction.CONTINUE

            if not success:
                return NextSocketAction.SUSPEND
            else:
                return NextSocketAction.CONTINUE

        except HttpException as e:
            tur.req.abort()
            tur.res.send_http_exception(tur_id, e)
            self.reset_state()
            return NextSocketAction.WRITE

    def handle_end_content(self, cmd):
        raise Sink()

    def req_finished(self):
        return self.state == H1InboundHandler.STATE_FINISHED

    def ship(self) -> InboundShip:
        return self.protocol_handler.ship

    ######################################################
    # Private methods
    ######################################################
    def change_state(self, new_state):
        self.state = new_state

    def reset_state(self):
        self.header_read = False
        self.change_state(H1InboundHandler.STATE_FINISHED)
        self.cur_tour = None

    def end_req_content(self, chk_tur_id, tur):
        tur.req.end_content(chk_tur_id)
        self.reset_state()

    def start_tour(self, tur):
        secure = self.ship().port_docker.secure
        HttpUtil.parse_host_port(tur, 443 if secure else 80)
        HttpUtil.parse_authorization(tur)

        skt = self.ship().rudder.key()
        if skt is None:
            raise Sink("%s Illegal state", self.ship)

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

        server_addr = skt.getsockname()
        tur.req.server_address = server_addr[0]
        tur.req.server_port = server_addr[1]

        tur.req.server_port = tur.req.req_port
        tur.req.server_name = tur.req.req_host
        tur.is_secure = secure

        tur.go()

