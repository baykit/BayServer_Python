from bayserver_core.docker.base.port_base import PortBase
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore

from bayserver_docker_ajp.ajp_docker import AjpDocker
from bayserver_docker_ajp.ajp_packet_factory import AjpPacketFactory
from bayserver_docker_ajp.ajp_inbound_handler import AjpInboundHandler


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
