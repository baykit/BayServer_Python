import ssl

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.config_exception import ConfigException

from bayserver_core.agent.transporter.plain_transporter import PlainTransporter
from bayserver_core.agent.transporter.secure_transporter import SecureTransporter
from bayserver_docker_http.h1.h1_packet_factory import H1PacketFactory
from bayserver_docker_http.h1.h1_warp_handler import H1WarpHandler
from bayserver_docker_http.h2.h2_packet_factory import H2PacketFactory
from bayserver_docker_http.h2.h2_warp_handler import H2WarpHandler
from bayserver_docker_http.htp_docker import HtpDocker
from bayserver_core.docker.warp.warp_docker import WarpDocker
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.util.io_util import IOUtil
from bayserver_core.util.string_util import StringUtil


class HtpWarpDocker(WarpDocker, HtpDocker):

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
                BayLog.error_e(e)
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

    def new_transporter(self, agt, skt):
        if self.secure:
            return SecureTransporter(self.ssl_ctx, False, IOUtil.get_sock_recv_buf_size(skt), self.trace_ssl)
        else:
            return PlainTransporter(False, IOUtil.get_sock_recv_buf_size(skt))

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



