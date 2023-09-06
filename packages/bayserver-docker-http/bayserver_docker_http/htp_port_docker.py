from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.docker.base.port_base import PortBase
from bayserver_docker_http.htp_docker import HtpDocker
from bayserver_core.util.string_util import StringUtil

from bayserver_docker_http.h1.h1_inbound_handler import H1InboundHandler
from bayserver_docker_http.h1.h1_packet_factory import H1PacketFactory
from bayserver_docker_http.h2.h2_inbound_handler import H2InboundHandler
from bayserver_docker_http.h2.h2_packet_factory import H2PacketFactory
from bayserver_docker_http.h2.h2_error_code import H2ErrorCode


class HtpPortDocker(PortBase, HtpDocker):

    DEFAULT_SUPPORT_H2 = True

    def __init__(self):
        PortBase.__init__(self)
        self.support_h2 = HtpPortDocker.DEFAULT_SUPPORT_H2

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        if self.support_h2:
            if(self.secure_docker is not None):
                self.secure_docker.set_app_protocols(["h2", "http/1.1"])
            H2ErrorCode.init_codes()

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "supporth2" or key == "enableh2":
            self.support_h2 = StringUtil.parse_bool(kv.value)
        else:
            return super().init_key_val(kv)

        return True

    ######################################################
    # Implements Port
    ######################################################

    def protocol(self):
        return HtpDocker.H1_PROTO_NAME


    ######################################################
    # Implements PortBase
    ######################################################
    def support_anchored(self):
        return True

    def support_unanchored(self):
        return False

    ######################################################
    # Class initializer
    ######################################################
    PacketStore.register_protocol(
        HtpDocker.H1_PROTO_NAME,
        H1PacketFactory()
    )
    PacketStore.register_protocol(
        HtpDocker.H2_PROTO_NAME,
        H2PacketFactory()
    )
    ProtocolHandlerStore.register_protocol(
        HtpDocker.H1_PROTO_NAME,
        True,
        H1InboundHandler.InboundProtocolHandlerFactory())
    ProtocolHandlerStore.register_protocol(
        HtpDocker.H2_PROTO_NAME,
        True,
        H2InboundHandler.InboundProtocolHandlerFactory())
