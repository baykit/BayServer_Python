import ssl
import traceback

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.agent.multiplexer.secure_transporter import SecureTransporter
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.ship.ship import Ship
from bayserver_core.symbol import Symbol
from bayserver_core.config_exception import ConfigException

from bayserver_docker_http.h1.h1_packet_factory import H1PacketFactory
from bayserver_docker_http.h1.h1_warp_handler import H1WarpHandler
from bayserver_docker_http.h2.h2_packet_factory import H2PacketFactory
from bayserver_docker_http.h2.h2_warp_handler import H2WarpHandler
from bayserver_docker_http.htp_docker import HtpDocker
from bayserver_core.docker.base.warp_base import WarpBase
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.util.io_util import IOUtil
from bayserver_core.util.string_util import StringUtil


class HtpWarpDocker(WarpBase, HtpDocker):

    def __init__(self):
        super().__init__()
        self.secure = False
        self.support_h2 = True
        self.ssl_ctx = None
        self.trace_ssl = False

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        if self.secure:
            try:
                self.ssl_ctx = ssl.create_default_context()
                self.ssl_ctx.check_hostname = False
                #self.ssl_ctx.verify_mode = ssl.CERT_OPTIONAL
                self.ssl_ctx.verify_mode = ssl.CERT_NONE
            except BaseException as e:
                BayLog.error_e(e, traceback.format_stack())
                raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_SSL_INIT_ERROR, e))

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "supporth2":
            self.support_h2 = StringUtil.parse_bool(kv.value)

        elif key == "tracessl":
            self.trace_ssl = StringUtil.parse_bool(kv.value)

        elif key == "secure":
            self.secure = StringUtil.parse_bool(kv.value)

        else:
            super().init_key_val(kv)

        return True;

    ######################################################
    # Implements WarpDocker
    ######################################################

    def secure(self):
        return self.secure

    ######################################################
    # Implements WarpDockerBase
    ######################################################

    def protocol(self):
        return HtpDocker.H1_PROTO_NAME

    def new_transporter(self, agt: GrandAgent, rd: SocketRudder, sip: Ship):
        if self.secure:
            app_protocols = ["h2"] if self.support_h2 else None
            tp = SecureTransporter(
                agt.net_multiplexer,
                sip,
                False,
                -1,
                self.trace_ssl,
                self.ssl_ctx,
                app_protocols)
        else:
            tp = PlainTransporter(
                agt.net_multiplexer,
                sip,
                False,
                IOUtil.get_sock_recv_buf_size(rd.key()),
                False
            )

        tp.init()
        return tp

    ######################################################
    # Class initializer
    ######################################################
    PacketStore.register_protocol(
        HtpDocker.H1_PROTO_NAME,
        H1PacketFactory())
    PacketStore.register_protocol(
        HtpDocker.H2_PROTO_NAME,
        H2PacketFactory())
    ProtocolHandlerStore.register_protocol(
        HtpDocker.H1_PROTO_NAME,
        False,
        H1WarpHandler.WarpProtocolHandlerFactory())
    ProtocolHandlerStore.register_protocol(
        HtpDocker.H2_PROTO_NAME,
        False,
        H2WarpHandler.WarpProtocolHandlerFactory())



