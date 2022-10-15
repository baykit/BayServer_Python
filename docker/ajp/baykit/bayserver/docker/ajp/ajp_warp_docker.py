from baykit.bayserver.agent.transporter.plain_transporter import PlainTransporter
from baykit.bayserver.protocol.packet_store import PacketStore
from baykit.bayserver.protocol.protocol_handler_store import ProtocolHandlerStore
from baykit.bayserver.docker.warp.warp_docker import WarpDocker
from baykit.bayserver.util.io_util import IOUtil

from baykit.bayserver.docker.ajp.ajp_docker import AjpDocker
from baykit.bayserver.docker.ajp.ajp_packet_factory import AjpPacketFactory
from baykit.bayserver.docker.ajp.ajp_warp_handler import AjpWarpHandler

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