from bayserver_core.sink import Sink
from bayserver_core.util.string_util import StringUtil

class PacketPartAccessor:

    def __init__(self, pkt, start, max_len):
        self.packet = pkt
        self.start = start
        self.max_len = max_len
        self.pos = 0

    def put_byte(self, b):
        buf = bytearray(1)
        buf[0] = b
        self.put_bytes(buf, 0, 1)

    def put_bytes(self, buf, ofs=0, length=None):
        if isinstance(buf, str):
            raise TypeError("buffer type error")

        if length is None:
            length = len(buf)
        if length > 0:
            self.check_write(length)
            self.packet.buf[self.start + self.pos: self.start + self.pos + length] = buf[ofs: ofs + length]
            self.forward(length)

    def put_short(self, val):
        h = val >> 8 & 0xFF
        l = val & 0xFF
        buf = bytearray()
        buf.append(h)
        buf.append(l)
        self.put_bytes(buf, 0, len(buf))

    def put_int(self, val):
        b1 = val >> 24 & 0xFF
        b2 = val >> 16 & 0xFF
        b3 = val >> 8 & 0xFF
        b4 = val & 0xFF
        buf = bytearray()
        buf.append(b1)
        buf.append(b2)
        buf.append(b3)
        buf.append(b4)
        self.put_bytes(buf, 0, len(buf))

    def put_string(self, s):
        if s is None:
            raise Sink()

        self.put_bytes(StringUtil.to_bytes(s))

    def get_byte(self):
        buf = bytearray(1)
        self.get_bytes(buf, 0, 1)
        return buf[0]

    def get_bytes(self, buf, ofs, length):
        if buf is None:
            raise Sink("buf is null")
        if not isinstance(buf, bytearray):
            raise Sink("buf is not a byte array")

        self.check_read(length)
        buf[ofs: ofs + length] = self.packet.buf[self.start + self.pos: self.start + self.pos + length]
        self.pos += length

    def get_short(self):
        h = self.get_byte()
        l = self.get_byte()
        return h << 8 | l

    def get_int(self):
        b1 = self.get_byte()
        b2 = self.get_byte()
        b3 = self.get_byte()
        b4 = self.get_byte()
        return b1 << 24 | b2 << 16 | b3 << 8 | b4

    def check_read(self, length):
        max_len = self.max_len if (self.max_len >= 0) else (self.packet.buf_len - self.start)
        if self.pos + length > max_len:
            raise Sink("Invalid array index")

    def check_write(self, length):
        if self.max_len > 0 and self.pos + length > self.max_len:
            raise Sink("Buffer overflow")

    def forward(self, length):
        self.pos += length

        if self.start + self.pos > self.packet.buf_len:
            self.packet.buf_len = self.start + self.pos





