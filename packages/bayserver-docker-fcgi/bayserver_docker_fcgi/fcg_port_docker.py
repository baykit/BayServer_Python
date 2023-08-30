from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore

from bayserver_core.docker.base.port_base import PortBase

from bayserver_docker_fcgi.fcg_docker import FcgDocker
from bayserver_docker_fcgi.fcg_packet_factory import FcgPacketFactory
from bayserver_docker_fcgi.fcg_inbount_handler import FcgInboundHandler


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