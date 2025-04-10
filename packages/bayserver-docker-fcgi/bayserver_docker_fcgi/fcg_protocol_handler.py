from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.command_packer import CommandPacker


from bayserver_docker_fcgi.fcg_docker import FcgDocker
from bayserver_docker_fcgi.fcg_handler import FcgHandler
from bayserver_docker_fcgi.fcg_packet import FcgPacket
from bayserver_docker_fcgi.fcg_command_unpacker import FcgCommandUnPacker
from bayserver_docker_fcgi.fcg_packet_unpacker import FcgPacketUnPacker


class FcgProtocolHandler(ProtocolHandler):

    def __init__(self,
                 h1_handler: FcgHandler,
                 packet_unpacker: FcgPacketUnPacker,
                 packet_packer: PacketPacker,
                 command_unpacker: FcgCommandUnPacker,
                 command_packer: CommandPacker,
                 svr_mode: bool):
        super().__init__(
            packet_unpacker,
            packet_packer,
            command_unpacker,
            command_packer,
            h1_handler,
            svr_mode
        )


    def __str__(self):
        return f"PH[{self.ship}]"

    ######################################################
    # Implements ProtocolHandler
    ######################################################
    def protocol(self):
        return FcgDocker.PROTO_NAME

    def max_req_packet_data_size(self):
        return FcgPacket.MAXLEN

    def max_res_packet_data_size(self):
        return FcgPacket.MAXLEN


