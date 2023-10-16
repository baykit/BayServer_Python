
from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink

from bayserver_core.tour.tour import Tour
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.docker.warp.warp_data import WarpData
from bayserver_core.docker.warp.warp_handler import WarpHandler

from bayserver_docker_http.h1.h1_protocol_handler import H1ProtocolHandler
from bayserver_docker_http.h1.command.cmd_header import CmdHeader
from bayserver_docker_http.h1.command.cmd_content import CmdContent
from bayserver_docker_http.h1.command.cmd_end_content import CmdEndContent

class H1WarpHandler(H1ProtocolHandler, WarpHandler):
    class WarpProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            return H1WarpHandler(pkt_store)

    STATE_READ_HEADER = 1
    STATE_READ_CONTENT = 2
    STATE_FINISHED = 3

    FIXED_WARP_ID = 1

    def __init__(self, pkt_store):
        super().__init__(pkt_store, False)
        self.state = None
        self.reset()


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
        return WarpData(self.ship, warp_id)

    def post_warp_headers(self, tur):
        twn = tur.town

        twn_path = twn.name
        if not twn_path.endswith("/"):
            twn_path += "/"

        sip = self.ship
        new_uri = sip.docker.warp_base + tur.req.uri[len(twn_path):]
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

        cmd.set_header(Headers.HOST, f"{sip.docker.host}:{sip.docker.port}")
        cmd.set_header(Headers.CONNECTION, "Keep-Alive")

        if BayServer.harbor.trace_header:
            for kv in cmd.headers:
                BayLog.info("%s warp_http reqHdr: %s=%s", tur, kv[0], kv[1])

        self.ship.post(cmd)

    def post_warp_contents(self, tur, buf, start, length, callback):
        cmd = CmdContent(buf, start, length)
        self.ship.post(cmd, callback)


    def post_warp_end(self, tur):
        cmd = CmdEndContent()
        def callback():
            self.ship.agent.non_blocking_handler.ask_to_read(self.ship.socket)

        self.ship.post(cmd, callback)


    def verify_protocol(self, proto):
        pass


    ######################################################
    # Implements H1CommandHandler
    ######################################################

    def handle_header(self, cmd):
        tur = self.ship.get_tour(H1WarpHandler.FIXED_WARP_ID)
        wdat = WarpData.get(tur)
        BayLog.debug("%s handleHeader status=%d", wdat, cmd.status);
        self.ship.keeping = False

        if self.state == H1WarpHandler.STATE_FINISHED:
            self.change_state(H1WarpHandler.STATE_READ_HEADER)

        if self.state != H1WarpHandler.STATE_READ_HEADER:
            raise ProtocolException("Header command not expected: state=%d", self.state)

        if BayServer.harbor.trace_header:
            BayLog.info("%s warp_http: resStatus: %d", wdat, cmd.status)

        for nv in cmd.headers:
            tur.res.headers.add(nv[0], nv[1])
            if BayServer.harbor.trace_header:
                BayLog.info("%s warp_http: resHeader: %s=%s", wdat, nv[0], nv[1]);

        tur.res.headers.status = cmd.status
        res_cont_len = tur.res.headers.content_length()
        tur.res.send_headers(Tour.TOUR_ID_NOCHECK)

        if res_cont_len == 0 or cmd.status == HttpStatus.NOT_MODIFIED:
            self.end_res_content(tur)
        else:
            self.change_state(H1WarpHandler.STATE_READ_CONTENT)
            sid = self.ship.id()

            def callback(len, resume):
                if resume:
                    self.ship.resume(sid)

            tur.res.set_consume_listener(callback)

        return NextSocketAction.CONTINUE

    def handle_content(self, cmd):
        tur = self.ship.get_tour(H1WarpHandler.FIXED_WARP_ID)
        wdat = WarpData.get(tur)
        BayLog.debug("%s handleContent len=%d posted=%d contLen=%d", wdat, cmd.length, tur.res.bytes_posted,
                     tur.res.bytes_limit);

        if self.state != H1WarpHandler.STATE_READ_CONTENT:
            raise ProtocolException("Content command not expected")

        available = tur.res.send_content(Tour.TOUR_ID_NOCHECK, cmd.buf, cmd.start, cmd.length)
        if tur.res.bytes_posted == tur.res.bytes_limit:
            self.end_res_content(tur)
            return NextSocketAction.CONTINUE
        elif not available:
            return NextSocketAction.SUSPEND

        else:
            return NextSocketAction.CONTINUE

    def handle_end_content(self, cmd):
        raise Sink()

    def req_finished(self):
        return self.state == H1WarpHandler.STATE_FINISHED


    #
    # private
    #
    def end_res_content(self, tur):
        self.ship.end_warp_tour(tur)
        tur.res.end_content(Tour.TOUR_ID_NOCHECK)
        self.reset()
        self.ship.keeping = True

    def change_state(self, new_state):
        self.state = new_state


