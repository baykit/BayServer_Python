from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_docker_http.h2.h2_command_unpacker import H2CommandUnPacker
from bayserver_docker_http.h2.h2_handler import H2Handler
from bayserver_docker_http.h2.h2_packet import H2Packet
from bayserver_docker_http.h2.h2_packet_unpacker import H2PacketUnPacker
from bayserver_docker_http.htp_docker import HtpDocker


class H2ProtocolHandler(ProtocolHandler):
    CTL_STREAM_ID = 0

    def __init__(self,
                 h1_handler: H2Handler,
                 packet_unpacker: H2PacketUnPacker,
                 packet_packer: PacketPacker,
                 command_unpacker: H2CommandUnPacker,
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


    ######################################################
    # Implements ProtocolHandler
    ######################################################

    def max_req_packet_data_size(self):
        return H2Packet.DEFAULT_PAYLOAD_MAXLEN

    def max_res_packet_data_size(self):
        return H2Packet.DEFAULT_PAYLOAD_MAXLEN

    def protocol(self):
        return HtpDocker.H2_PROTO_NAME


