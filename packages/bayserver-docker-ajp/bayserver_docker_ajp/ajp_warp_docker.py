from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.docker.base.warp_base import WarpBase
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.ship.ship import Ship
from bayserver_core.util.io_util import IOUtil

from bayserver_docker_ajp.ajp_docker import AjpDocker
from bayserver_docker_ajp.ajp_packet_factory import AjpPacketFactory
from bayserver_docker_ajp.ajp_warp_handler import AjpWarpHandler

class AjpWarpDocker(WarpBase, AjpDocker):

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

    def new_transporter(self, agt: GrandAgent, rd: SocketRudder, sip: Ship):
        return PlainTransporter(
            agt.net_multiplexer,
            sip,
            False,
            IOUtil.get_sock_recv_buf_size(rd.key()),
            False)

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