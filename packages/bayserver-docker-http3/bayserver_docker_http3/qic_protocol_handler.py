from typing import Dict

from bayserver_core.common.inbound_handler import InboundHandler
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.command_unpacker import CommandUnPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.packet_unpacker import PacketUnPacker
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_core.sink import Sink
from bayserver_docker_http3 import h3port_docker as h3
from bayserver_docker_http3.qic_handler import QicHandler


class QicProtocolHandler(ProtocolHandler, InboundHandler):

    MAX_H3_PACKET_SIZE = 1024

    handlers: Dict[bytes, ProtocolHandler] = []

#    def __init__(self, con, adr, cfg, postman):
#        super().__init__()
#        self.con = con
#        self.sender = adr
#        self.config = cfg
#        self.postman = postman
 #       self.hcon = None
 #       self.last_accessed = None

    def __init__(self,
                 qic_handler: QicHandler,
                 packet_unpacker: PacketUnPacker,
                 packet_packer: PacketPacker,
                 command_unpacker: CommandUnPacker,
                 command_packer: CommandPacker,
                 svr_mode: bool):
        super().__init__(
            packet_unpacker,
            packet_packer,
            command_unpacker,
            command_packer,
            qic_handler,
            svr_mode
        )

        packet_unpacker.set_protocol_handler(self)


    def __str__(self):
        return f"{self.ship}"


    ######################################################
    # Implements ProtocolHandler
    ######################################################

    def protocol(self):
        return "h3"

    def max_req_packet_data_size(self):
        return QicProtocolHandler.MAX_H3_PACKET_SIZE

    def max_res_packet_data_size(self):
        #return QicProtocolHandler.MAX_H3_PACKET_SIZE
        return 16000


    ######################################################
    # Implements InboundHandler
    ######################################################

    def send_res_headers(self, tur):
        raise Sink()

    def send_res_content(self, tur, bytes, ofs, len, callback):
        raise Sink()

    def send_end_tour(self, tur, keep_alive, callback):
        raise Sink()

    def on_protocol_error(self, protocol_ex):
        raise Sink()





    ######################################################
    # Custom methods
    ######################################################

    def port_docker(self) -> "h3.H3PortDocker":
        return self.ship.get_port_docker()



