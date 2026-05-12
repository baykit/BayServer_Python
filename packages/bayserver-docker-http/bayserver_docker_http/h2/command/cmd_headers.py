from bayserver_core.protocol.protocol_exception import ProtocolException

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

    def __init__(self, stream_id=0, flags=None):
        super().__init__(H2Type.HEADERS, stream_id, flags)
        self.header_blocks = []
        self.pad_length = 0
        self.excluded = False
        self.stream_dependency = 0
        self.weight = 0
        # Raw header-block fragment (data is from packet buf; start/length
        # relative to it). Captured for the multi-frame HEADERS+CONTINUATION
        # case where the HPACK block must be decoded only after the final
        # CONTINUATION's END_HEADERS arrives — parsing mid-block can split
        # a literal field representation.
        self.data = None
        self.start = 0
        self.length = 0

    def init(self, stream_id, flags=None):
        super().init(stream_id, flags)
        self.header_blocks.clear()
        self.pad_length = 0
        self.excluded = False
        self.stream_dependency = 0
        self.weight = 0
        self.data = None
        self.start = 0
        self.length = 0

    def reset(self):
        super().reset()
        self.header_blocks.clear()
        self.pad_length = 0
        self.excluded = False
        self.stream_dependency = 0
        self.weight = 0
        self.data = None
        self.start = 0
        self.length = 0

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
            # RFC 7540 § 5.3.1: a stream MUST NOT depend on itself.
            if self.stream_dependency == self.stream_id:
                raise ProtocolException(
                    f"HEADERS stream depends on itself: {self.stream_id}")

        # RFC 7540 § 6.2: padding length must leave at least one octet of payload.
        block_end = pkt.data_len() - self.pad_length
        if block_end < acc.pos:
            raise ProtocolException(
                f"HEADERS pad length exceeds payload: pad={self.pad_length}")

        # Capture the raw header-block fragment. Parsing the HPACK content is
        # deferred to the inbound handler, because HPACK encoding can span
        # HEADERS + CONTINUATION boundaries and parsing mid-block would split
        # a literal field representation. Copy out of the pooled packet buffer
        # because the packet is returned to the store right after dispatch.
        body_start = pkt.header_len + acc.pos
        body_len = block_end - acc.pos
        self.data = bytes(pkt.buf[body_start: body_start + body_len])
        self.start = 0
        self.length = body_len

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
        # RFC 7541 § 4.2: dynamic-table size updates must appear at the very
        # start of a header block. Once any other representation is seen,
        # subsequent size updates are a decoding error.
        seen_non_size_update = False
        while acc.pos < length:
            blk = HeaderBlock.unpack(acc)
            if blk.op == HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE:
                if seen_non_size_update:
                    raise ProtocolException(
                        "Dynamic table size update must appear at the start of a header block")
            else:
                seen_non_size_update = True
            self.header_blocks.append(blk)

    def write_header_block(self, acc):
        for blk in self.header_blocks:
            HeaderBlock.pack(blk, acc)


    def add_header_block(self, blk):
        self.header_blocks.append(blk)





