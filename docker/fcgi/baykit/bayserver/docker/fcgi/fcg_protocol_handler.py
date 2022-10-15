from baykit.bayserver.protocol.protocol_handler import ProtocolHandler
from baykit.bayserver.protocol.packet_packer import PacketPacker
from baykit.bayserver.protocol.command_packer import CommandPacker


from baykit.bayserver.docker.fcgi.fcg_docker import FcgDocker
from baykit.bayserver.docker.fcgi.fcg_packet import FcgPacket
from baykit.bayserver.docker.fcgi.fcg_command_unpacker import FcgCommandUnPacker
from baykit.bayserver.docker.fcgi.fcg_packet_unpacker import FcgPacketUnPacker


class FcgProtocolHandler(ProtocolHandler, FcgCommandUnPacker):

    def __init__(self, pkt_store, svr_mode):
        super().__init__()
        self.command_unpacker = FcgCommandUnPacker(self)
        self.packet_unpacker = FcgPacketUnPacker(pkt_store, self.command_unpacker)
        self.packet_packer = PacketPacker()
        self.command_packer = CommandPacker(self.packet_packer, pkt_store)
        self.server_mode = svr_mode


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


