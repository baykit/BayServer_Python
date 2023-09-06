from bayserver_core.bay_log import BayLog
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.packet_unpacker import PacketUnPacker
from bayserver_core.util.simple_buffer import SimpleBuffer

from bayserver_docker_fcgi.fcg_packet import FcgPacket

class FcgPacketUnPacker(PacketUnPacker):
    STATE_READ_PREAMBLE = 1  # #state for reading first 8 bytes (from version to reserved)
    STATE_READ_CONTENT = 2  # state for reading content data
    STATE_READ_PADDING = 3  # state for reading padding data
    STATE_END = 4  # End

    def __init__(self, pkt_store, cmd_unpacker):
        self.cmd_unpacker = cmd_unpacker
        self.pkt_store = pkt_store
        self.header_buf = SimpleBuffer()
        self.data_buf = SimpleBuffer()
        self.state = None
        self.version = None
        self.type = None
        self.req_id = None
        self.length = None
        self.padding = None
        self.padding_read_bytes = None
        self.cont_len = None
        self.read_bytes = None
        self.reset()

    def reset(self):
        self.state = FcgPacketUnPacker.STATE_READ_PREAMBLE
        self.version = 0
        self.type = None
        self.req_id = 0
        self.length = 0
        self.padding = 0
        self.padding_read_bytes = 0
        self.cont_len = 0
        self.read_bytes = 0
        self.header_buf.reset()
        self.data_buf.reset()

    def bytes_received(self, buf):
        next_suspend = False
        next_write = False
        pos = 0

        while pos < len(buf):
            while self.state != FcgPacketUnPacker.STATE_END and pos < len(buf):

                if self.state == FcgPacketUnPacker.STATE_READ_PREAMBLE:
                    # preamble read mode
                    length = FcgPacket.PREAMBLE_SIZE - len(self.header_buf)
                    if len(buf) - pos < length:
                        length = len(buf) - pos

                    self.header_buf.put(buf, pos, length)
                    pos += length

                    if len(self.header_buf) == FcgPacket.PREAMBLE_SIZE:
                        self.header_read_done()
                        if self.length == 0:
                            if self.padding == 0:
                                self.change_state(FcgPacketUnPacker.STATE_END)
                            else:
                                self.change_state(FcgPacketUnPacker.STATE_READ_PADDING)

                        else:
                            self.change_state(FcgPacketUnPacker.STATE_READ_CONTENT)


                elif self.state == FcgPacketUnPacker.STATE_READ_CONTENT:
                    # content read mode
                    length = self.length - len(self.data_buf)
                    if length > len(buf) - pos:
                        length = len(buf) - pos

                    if length > 0:
                        self.data_buf.put(buf, pos, length)
                        pos += length

                        if len(self.data_buf) == self.length:
                            if self.padding == 0:
                                self.change_state(FcgPacketUnPacker.STATE_END)
                            else:
                                self.change_state(FcgPacketUnPacker.STATE_READ_PADDING)


                elif self.state == FcgPacketUnPacker.STATE_READ_PADDING:
                    # padding read mode
                    length = self.padding - self.padding_read_bytes

                    if length > len(buf) - pos:
                        length = len(buf) - pos

                    # self.data_buf.put(buf, pos, len)
                    pos += length

                    if length > 0:
                        self.padding_read_bytes += length

                        if self.padding_read_bytes == self.padding:
                            self.change_state(FcgPacketUnPacker.STATE_END)

                else:
                  raise RuntimeError("IllegalState")

            if self.state == FcgPacketUnPacker.STATE_END:
                pkt = self.pkt_store.rent(self.type)
                pkt.req_id = self.req_id
                pkt.new_header_accessor().put_bytes(self.header_buf.buf, 0, len(self.header_buf))
                pkt.new_data_accessor().put_bytes(self.data_buf.buf, 0, len(self.data_buf))

                try:
                    state = self.cmd_unpacker.packet_received(pkt)
                finally:
                    self.pkt_store.Return(pkt)

                self.reset()

                if self.state == NextSocketAction.SUSPEND:
                    next_suspend = True
                elif self.state == NextSocketAction.CONTINUE:
                    pass
                elif self.state == NextSocketAction.WRITE:
                    next_write = True
                elif self.state == NextSocketAction.CLOSE:
                    return state

        if next_write:
            return NextSocketAction.WRITE
        elif next_suspend:
            return NextSocketAction.SUSPEND
        else:
            return NextSocketAction.CONTINUE

    def change_state(self, new_state):
        self.state = new_state

    def header_read_done(self):
        pre = self.header_buf.buf
        self.version = self.byte_to_int(pre[0])
        self.type = self.byte_to_int(pre[1])
        self.req_id = self.bytes_to_int(pre[2], pre[3])
        self.length = self.bytes_to_int(pre[4], pre[5])
        self.padding = self.byte_to_int(pre[6])
        reserved = self.byte_to_int(pre[7])
        BayLog.debug("fcg: read packet header: version=%s type=%d reqId=%d length=%d padding=%d",
                     self.version, self.type, self.req_id, self.length, self.padding)

    def byte_to_int(self, b):
        return b & 0xff

    def bytes_to_int(self, b1, b2):
        return self.byte_to_int(b1) << 8 | self.byte_to_int(b2)
