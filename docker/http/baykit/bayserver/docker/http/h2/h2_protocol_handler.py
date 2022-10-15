from baykit.bayserver.protocol.command_packer import CommandPacker
from baykit.bayserver.protocol.packet_packer import PacketPacker
from baykit.bayserver.protocol.protocol_handler import ProtocolHandler


from baykit.bayserver.docker.http.htp_docker import HtpDocker
from baykit.bayserver.docker.http.h2.h2_command_unpacker import H2CommandUnPacker
from baykit.bayserver.docker.http.h2.h2_command_handler import H2CommandHandler
from baykit.bayserver.docker.http.h2.h2_packet import H2Packet
from baykit.bayserver.docker.http.h2.h2_packet_unpacker import H2PacketUnPacker
from baykit.bayserver.docker.http.h2.header_table import HeaderTable

class H2ProtocolHandler(ProtocolHandler, H2CommandHandler):
    CTL_STREAM_ID = 0

    def __init__(self, pkt_store, svr_mode):
        super().__init__()
        self.command_unpacker = H2CommandUnPacker(self)
        self.packet_unpacker = H2PacketUnPacker(self.command_unpacker, pkt_store, svr_mode)
        self.packet_packer = PacketPacker()
        self.command_packer = CommandPacker(self.packet_packer, pkt_store)
        self.server_mode = svr_mode
        self.req_header_tbl = HeaderTable.create_dynamic_table()
        self.res_header_tbl = HeaderTable.create_dynamic_table()



    ######################################################
    # Implements ProtocolHandler
    ######################################################

    def max_req_packet_data_size(self):
        return H2Packet.DEFAULT_PAYLOAD_MAXLEN

    def max_res_packet_data_size(self):
        return H2Packet.DEFAULT_PAYLOAD_MAXLEN

    def protocol(self):
        return HtpDocker.H2_PROTO_NAME


