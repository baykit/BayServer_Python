from bayserver_core.protocol.packet_part_accessor import PacketPartAccessor
from bayserver_core.util.reusable import Reusable
from bayserver_core.util.class_util import ClassUtil

class Packet(Reusable):
    INITIAL_BUF_SIZE = 8192 * 4

    def __init__(self, type, header_len, max_data_len):
        self.type = type
        self.header_len = header_len
        self.max_data_len = max_data_len
        self.buf = bytearray(Packet.INITIAL_BUF_SIZE)
        self.buf_len = None
        self.reset()

    def reset(self):
        self.buf.clear()
        for i in range(self.header_len):
            self.buf.append(0)
        self.buf_len = self.header_len

    def data_len(self):
        return self.buf_len - self.header_len

    def new_header_accessor(self):
        return PacketPartAccessor(self, 0, self.header_len)

    def new_data_accessor(self):
        return PacketPartAccessor(self, self.header_len, -1)

    def __str__(self):
        return f"pkt[{ClassUtil.get_local_name(type(self))}({self.type})]"
