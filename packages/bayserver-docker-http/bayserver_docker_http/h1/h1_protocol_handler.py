from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_docker_http.h1.h1_command_unpacker import H1CommandUnPacker
from bayserver_docker_http.h1.h1_handler import H1Handler
from bayserver_docker_http.h1.h1_packet import H1Packet
from bayserver_docker_http.h1.h1_packet_unpacker import H1PacketUnPacker
from bayserver_docker_http.htp_docker import HtpDocker


class H1ProtocolHandler(ProtocolHandler):

    keeping: bool

    def __init__(self,
                 h1_handler: H1Handler,
                 packet_unpacker: H1PacketUnPacker,
                 packet_packer: PacketPacker,
                 command_unpacker: H1CommandUnPacker,
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
        self.keeping = False

    ######################################################
    # Implements Reusable
    ######################################################
    def reset(self):
        super().reset()
        self.keeping = False

    ######################################################
    # Implements ProtocolHandler
    ######################################################
    def max_req_packet_data_size(self):
        return H1Packet.MAX_DATA_LEN

    def max_res_packet_data_size(self):
        return H1Packet.MAX_DATA_LEN

    def protocol(self):
        return HtpDocker.H1_PROTO_NAME

