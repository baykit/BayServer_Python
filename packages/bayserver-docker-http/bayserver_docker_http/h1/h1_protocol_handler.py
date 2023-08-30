from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.command_packer import CommandPacker

from bayserver_docker_http.h1.h1_command_unpacker import H1CommandUnPacker
from bayserver_docker_http.h1.h1_packet_unpacker import H1PacketUnPacker
from bayserver_docker_http.h1.h1_command_handler import H1CommandHandler
from bayserver_docker_http.h1.h1_packet import H1Packet

from bayserver_docker_http.htp_docker import HtpDocker

class H1ProtocolHandler(ProtocolHandler, H1CommandHandler):

    def __init__(self, pkt_store, svr_mode):
        super().__init__()
        self.command_unpacker = H1CommandUnPacker(self, svr_mode)
        self.packet_unpacker = H1PacketUnPacker(self.command_unpacker, pkt_store)
        self.packet_packer = PacketPacker()
        self.command_packer = CommandPacker(self.packet_packer, pkt_store)
        self.server_mode = svr_mode
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

