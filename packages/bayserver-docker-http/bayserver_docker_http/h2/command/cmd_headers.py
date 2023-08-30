from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_packet import H2Packet
from bayserver_docker_http.h2.header_block import HeaderBlock

#
#  HTTP/2 Header payload format
#
#  +---------------+
#  |Pad Length? (8)|
#  +-+-------------+-----------------------------------------------+
#  |E|                 Stream Dependency? (31)                     |
#  +-+-------------+-----------------------------------------------+
#  |  Weight? (8)  |
#  +-+-------------+-----------------------------------------------+
#  |                   Header Block Fragment (*)                 ...
#  +---------------------------------------------------------------+
#  |                           Padding (*)                       ...
#  +---------------------------------------------------------------+
#

class CmdHeaders(H2Command):

    def __init__(self, stream_id, flags=None):
        super().__init__(H2Type.HEADERS, stream_id, flags)
        self.header_blocks = []
        self.pad_length = 0
        self.excluded = False
        self.stream_dependency = 0
        self.weight = 0

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_h2_data_accessor()

        if pkt.flags.padded():
            self.pad_length = acc.get_byte()

        if pkt.flags.priority():
            val = acc.get_int()
            self.excluded = H2Packet.extract_flag(val) == 1
            self.stream_dependency = H2Packet.extract_int31(val)
            self.weight = acc.get_byte()

        self.read_header_block(acc, pkt.data_len())

    def pack(self, pkt):
        acc = pkt.new_h2_data_accessor()

        if self.flags.padded():
            acc.put_byte(self.pad_length)

        if self.flags.priority():
            acc.put_int(H2Packet.make_stream_depency32(self.excluded, self.stream_depency))
            acc.put_byte(self.weight)

        self.write_header_block(acc)
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_headers(self)

    def read_header_block(self, acc, length):
        while acc.pos < length:
            blk = HeaderBlock.unpack(acc)
            self.header_blocks.append(blk)

    def write_header_block(self, acc):
        for blk in self.header_blocks:
            HeaderBlock.pack(blk, acc)


    def add_header_block(self, blk):
        self.header_blocks.append(blk)





