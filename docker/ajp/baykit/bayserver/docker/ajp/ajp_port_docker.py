from baykit.bayserver.docker.base.port_base import PortBase
from baykit.bayserver.protocol.packet_store import PacketStore
from baykit.bayserver.protocol.protocol_handler_store import ProtocolHandlerStore

from baykit.bayserver.docker.ajp.ajp_docker import AjpDocker
from baykit.bayserver.docker.ajp.ajp_packet_factory import AjpPacketFactory
from baykit.bayserver.docker.ajp.ajp_inbound_handler import AjpInboundHandler


class AjpPortDocker(PortBase, AjpDocker):

    ######################################################
    # Implements Port
    ######################################################
    def protocol(self):
        return AjpDocker.PROTO_NAME


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
        AjpDocker.PROTO_NAME,
        AjpPacketFactory()
    )
    ProtocolHandlerStore.register_protocol(
        AjpDocker.PROTO_NAME,
        True,
        AjpInboundHandler.InboundProtocolHandlerFactory())
