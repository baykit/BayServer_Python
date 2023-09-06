from bayserver_core.protocol.packet import Packet
from bayserver_core.protocol.packet_part_accessor import PacketPartAccessor

from bayserver_core.util.string_util import StringUtil

from bayserver_docker_http.h2.h2_flags import H2Flags
from bayserver_docker_http.h2.huffman.htree import HTree

#
#   Http2 spec
#     https://www.rfc-editor.org/rfc/rfc7540.txt
#
#   Http2 Frame format
#   +-----------------------------------------------+
#   |                 Length (24)                   |
#   +---------------+---------------+---------------+
#   |   Type (8)    |   Flags (8)   |
#   +-+-+-----------+---------------+-------------------------------+
#   |R|                 Stream Identifier (31)                      |
#   +=+=============================================================+
#   |                   Frame Payload (0...)                      ...
#   +---------------------------------------------------------------+
#

class H2Packet(Packet):

    class H2HeaderAccessor(PacketPartAccessor):
        def __init__(self, pkt, start, max_len):
            super().__init__(pkt, start, max_len)

        def put_int24(self, length):
            b1 = (length >> 16) & 0xFF
            b2 = (length >> 8) & 0xFF
            b3 = length & 0xFF
            buf = bytearray(3)
            buf[0] = b1
            buf[1] = b2
            buf[2] = b3
            self.put_bytes(buf)

    class H2DataAccessor(PacketPartAccessor):
        def __init__(self, pkt, start, max_len):
            super().__init__(pkt, start, max_len)

        def get_hpack_int(self, prefix, head):
            max_val = 0xFF >> (8 - prefix)

            first_byte = self.get_byte()
            first_val = first_byte & max_val
            head[0] = first_byte >> prefix
            if first_val != max_val:
                return first_val
            else:
                return max_val + self.get_hpack_int_rest()

        def get_hpack_int_rest(self):
            rest = 0
            i = 0
            while True:
                data = self.get_byte()
                cont = (data & 0x80) != 0
                value = data & 0x7F
                rest = rest + (value << (i * 7))
                if not cont:
                    break
                i += 1
            return rest

        def get_hpack_string(self):
            is_huffman = [None]
            length = self.get_hpack_int(7, is_huffman)
            data = bytearray(length)
            self.get_bytes(data, 0, length)
            if is_huffman[0] == 1:
                return HTree.decode(data)
            else:
                # ASCII
                return StringUtil.from_bytes(data)

        def put_hpack_int(self, val, prefix, head):
            max_val = 0xFF >> (8 - prefix)
            head_val = (head << prefix) & 0xFF
            if val < max_val:
                self.put_byte(val | head_val)
            else:
                self.put_byte(head_val | max_val)
                self.put_hpack_int_rest(val - max_val)

        def put_hpack_int_rest(self, val):
            while True:
                data = val & 0x7F
                next_val = val >> 7
                if next_val == 0:
                    self.put_byte(data)
                    break
                else:
                    self.put_byte(data | 0x80)
                    val = next_val

        def put_hpack_string(self, value, is_haffman):
            if is_haffman:
                raise RuntimeError("Illegal State")
            else:
                self.put_hpack_int(len(value), 7, 0)
                self.put_bytes(value.encode("us-ascii"))

    MAX_PAYLOAD_LEN = 0x00FFFFFF  # = 2^24-1 = 16777215 = 16MB-1
    DEFAULT_PAYLOAD_MAXLEN = 0x00004000  # = 2^14 = 16384 = 16KB
    FRAME_HEADER_LEN = 9

    NO_ERROR = 0x0
    PROTOCOL_ERROR = 0x1
    INTERNAL_ERROR = 0x2
    FLOW_CONTROL_ERROR = 0x3
    SETTINGS_TIMEOUT = 0x4
    STREAM_CLOSED = 0x5
    FRAME_SIZE_ERROR = 0x6
    REFUSED_STREAM = 0x7
    CANCEL = 0x8
    COMPRESSION_ERROR = 0x9
    CONNECT_ERROR = 0xa
    ENHANCE_YOUR_CALM = 0xb
    INADEQUATE_SECURITY = 0xc
    HTTP_1_1_REQUIRED = 0xd

    def __init__(self, typ):
        super().__init__(typ, H2Packet.FRAME_HEADER_LEN, H2Packet.DEFAULT_PAYLOAD_MAXLEN)
        self.flags = H2Flags.FLAGS_NONE
        self.stream_id = -1

    def reset(self):
        self.flags = H2Flags.FLAGS_NONE
        self.stream_id = -1
        super().reset()

    def __str__(self):
        return f"H2Packet({self.type}) headerLen={self.header_len} dataLen={self.data_len()} stm={self.stream_id} flags={self.flags}"

    def pack_header(self):
        acc = self.new_h2_header_accessor()
        acc.put_int24(self.data_len())
        acc.put_byte(self.type)
        acc.put_byte(self.flags.flags)
        acc.put_int(H2Packet.extract_int31(self.stream_id))

    def new_h2_header_accessor(self):
        return H2Packet.H2HeaderAccessor(self, 0, self.header_len)

    def new_h2_data_accessor(self):
        return H2Packet.H2DataAccessor(self, self.header_len, -1)

    @classmethod
    def extract_int31(cls, val):
        return val & 0x7FFFFFFF


    @classmethod
    def extract_flag(cls, val):
        return (val & 0x80000000) >> 31 & 1

    @classmethod
    def consolidate_flag_and_int32(cls, flag, val):
        return ((flag & 1) << 31) | (val & 0x7FFFFFFF)


    @classmethod
    def make_stream_depency32(cls, excluded, dep):
        return (1 if excluded else 0) << 31 | H2Packet.extract_int31(dep)


