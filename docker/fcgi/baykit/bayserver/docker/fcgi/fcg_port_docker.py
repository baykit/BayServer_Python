from baykit.bayserver.protocol.packet_store import PacketStore
from baykit.bayserver.protocol.protocol_handler_store import ProtocolHandlerStore

from baykit.bayserver.docker.base.port_base import PortBase

from baykit.bayserver.docker.fcgi.fcg_docker import FcgDocker
from baykit.bayserver.docker.fcgi.fcg_packet_factory import FcgPacketFactory
from baykit.bayserver.docker.fcgi.fcg_inbount_handler import FcgInboundHandler


class FcgPortDocker(PortBase, FcgDocker):

    ######################################################
    # Implements Port
    ######################################################
    def protocol(self):
        return super().PROTO_NAME

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
        FcgDocker.PROTO_NAME,
        FcgPacketFactory())
    ProtocolHandlerStore.register_protocol(
        FcgDocker.PROTO_NAME,
        True,
        FcgInboundHandler.InboundProtocolHandlerFactory())