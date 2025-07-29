from bayserver_core.protocol.command_handler import CommandHandler
from bayserver_core.protocol.protocol_handler import ProtocolHandler


class H3ProtocolHandler(ProtocolHandler):

    command_handler: CommandHandler
    MAX_H3_PACKET_SIZE = 1024

    def __init__(self, h: CommandHandler):
        super().__init__(None, None, None, None, h, True)
        self.command_handler = h


    def protocol(self):
        return "h3"

    def max_req_packet_data_size(self):
        return self.MAX_H3_PACKET_SIZE

    def max_res_packet_data_size(self):
        return self.MAX_H3_PACKET_SIZE
