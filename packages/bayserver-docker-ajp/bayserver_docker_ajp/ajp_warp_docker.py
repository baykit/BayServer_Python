from bayserver_core.agent.transporter.plain_transporter import PlainTransporter
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.docker.warp.warp_docker import WarpDocker
from bayserver_core.util.io_util import IOUtil

from bayserver_docker_ajp.ajp_docker import AjpDocker
from bayserver_docker_ajp.ajp_packet_factory import AjpPacketFactory
from bayserver_docker_ajp.ajp_warp_handler import AjpWarpHandler

class AjpWarpDocker(WarpDocker, AjpDocker):

    ######################################################
    # Implements WarpDocker
    ######################################################
    def secure(self):
        return False

    ######################################################
    # Implements WarpDockerBase
    ######################################################
    def protocol(self):
        return AjpDocker.PROTO_NAME

    def new_transporter(self, agt, skt):
        return PlainTransporter(False, IOUtil.get_sock_recv_buf_size(skt))

    ######################################################
    # Class initializer
    ######################################################
    PacketStore.register_protocol(
        AjpDocker.PROTO_NAME,
        AjpPacketFactory()
    )
    ProtocolHandlerStore.register_protocol(
        AjpDocker.PROTO_NAME,
        False,
        AjpWarpHandler.WarpProtocolHandlerFactory())