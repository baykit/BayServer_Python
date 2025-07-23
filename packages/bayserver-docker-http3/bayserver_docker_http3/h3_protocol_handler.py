from bayserver_core.protocol.command_handler import CommandHandler
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_docker_http3.qic_protocol_handler import QicProtocolHandler


class H3ProtocolHandler(ProtocolHandler):

    command_handler: CommandHandler

    def __init__(self, th: CommandHandler):
        super().__init__(None, None, None, None, th, True)
        self.command_handler = th


    def protocol(self):
        return "h3"

    def max_req_packet_data_size(self):
        return QicProtocolHandler.MAX_H3_PACKET_SIZE

    def max_res_packet_data_size(self):
        #return QicProtocolHandler.MAX_H3_PACKET_SIZE
        return 16000