from bayserver_docker_ajp.ajp_command import AjpCommand
from bayserver_docker_ajp.ajp_packet import AjpPacket
from bayserver_docker_ajp.ajp_type import AjpType

#
#  Data command format
#
#  AJP13_DATA :=
#    len, raw data
#

class CmdData(AjpCommand):
    LENGTH_OF_SIZE = 2
    MAX_DATA_LEN = AjpPacket.MAX_DATA_LEN - LENGTH_OF_SIZE

    def __init__(self, data=None, start=0, length=0):
        super().__init__(AjpType.DATA, True)
        self.data = data
        self.start = start
        self.length = length

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_ajp_data_accessor()
        self.length = acc.get_short()
        self.data = pkt.buf
        self.start = pkt.header_len + 2

    def pack(self, pkt):
        acc = pkt.new_ajp_data_accessor()
        acc.put_short(self.length)
        acc.put_bytes(self.data, self.start, self.length)

        # BayLog.debug "pack AJP command data: #{pkt.data.bytes}"

        #  must be called from last line
        super().pack(pkt)

    def handle(self, handler):
        return handler.handle_data(self)