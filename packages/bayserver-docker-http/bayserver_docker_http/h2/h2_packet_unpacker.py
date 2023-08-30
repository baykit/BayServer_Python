from bayserver_core.bay_log import BayLog
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.simple_buffer import SimpleBuffer

from bayserver_core.protocol.packet_unpacker import PacketUnPacker

from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_packet import H2Packet
from bayserver_docker_http.h2.h2_flags import H2Flags


class H2PacketUnPacker(PacketUnPacker):
    class FrameHeaderItem:

        def __init__(self, start, length):
            self.start = start
            self.len = length
            self.pos = 0

        def get(self, buf, index):
            return buf.buf[self.start + index]

    STATE_READ_LENGTH = 1
    STATE_READ_TYPE = 2
    STATE_READ_FLAGS = 3
    STATE_READ_STREAM_IDENTIFIER = 4
    STATE_READ_FLAME_PAYLOAD = 5
    STATE_END = 6

    FRAME_LEN_LENGTH = 3
    FRAME_LEN_TYPE = 1
    FRAME_LEN_FLAGS = 1
    FRAME_LEN_STREAM_IDENTIFIER = 4

    FLAGS_END_STREAM = 0x1
    FLAGS_END_HEADERS = 0x4
    FLAGS_PADDED = 0x8
    FLAGS_PRIORITY = 0x20

    CONNECTION_PREFACE = "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n".encode("us-ascii")

    def __init__(self, cmd_unpacker, pkt_store, server_mode):
        self.state = None
        self.tmp_buf = None
        self.item = None
        self.preface_read = None
        self.type = None
        self.payload_len = None
        self.flags = None
        self.stream_id = None

        self.cont_len = None
        self.read_bytes = None
        self.pos = None
        self.cmd_unpacker = cmd_unpacker
        self.pkt_store = pkt_store
        self.server_mode = server_mode
        self.tmp_buf = SimpleBuffer()
        self.reset()

    def reset(self):
        self.reset_state()
        self.preface_read = False

    def reset_state(self):
        self.change_state(H2PacketUnPacker.STATE_READ_LENGTH)
        self.item = H2PacketUnPacker.FrameHeaderItem(0, H2PacketUnPacker.FRAME_LEN_LENGTH)
        self.cont_len = 0
        self.read_bytes = 0
        self.tmp_buf.reset()
        self.type = None
        self.flags = 0
        self.stream_id = 0
        self.payload_len = 0

    def bytes_received(self, buf):
        suspend = False

        self.pos = 0
        if self.server_mode and not self.preface_read:
            length = len(H2PacketUnPacker.CONNECTION_PREFACE) - len(self.tmp_buf)
            if length > len(buf):
                length = len(buf)

            self.tmp_buf.put(buf, self.pos, length)
            self.pos += length
            if len(self.tmp_buf) == len(H2PacketUnPacker.CONNECTION_PREFACE):
                for i in range(len(self.tmp_buf)):
                    if H2PacketUnPacker.CONNECTION_PREFACE[i] != self.tmp_buf.buf[i]:
                        raise ProtocolException("Invalid connection preface: %s", self.tmp_buf.buf[0:len(self.tmp_buf)])

                pkt = self.pkt_store.rent(H2Type.PREFACE)
                pkt.new_data_accessor().put_bytes(self.tmp_buf.buf, 0, len(self.tmp_buf))
                nstat = self.cmd_unpacker.packet_received(pkt)
                self.pkt_store.Return(pkt)
                if nstat != NextSocketAction.CONTINUE:
                    return nstat

                BayLog.debug("h2: Connection preface OK")
                self.preface_read = True
                self.tmp_buf.reset()

        while self.state != H2PacketUnPacker.STATE_END and self.pos < len(buf):
            if self.state == H2PacketUnPacker.STATE_READ_LENGTH:
                if self.read_header_item(buf):
                    self.payload_len = ((self.item.get(self.tmp_buf, 0) & 0xFF) << 16 |
                                        (self.item.get(self.tmp_buf, 1) & 0xFF) << 8 |
                                        (self.item.get(self.tmp_buf, 2) & 0xFF))
                    self.item = H2PacketUnPacker.FrameHeaderItem(len(self.tmp_buf), H2PacketUnPacker.FRAME_LEN_TYPE)
                    self.change_state(H2PacketUnPacker.STATE_READ_TYPE)


            elif self.state == H2PacketUnPacker.STATE_READ_TYPE:
                if self.read_header_item(buf):
                    self.type = self.item.get(self.tmp_buf, 0)
                    self.item = H2PacketUnPacker.FrameHeaderItem(len(self.tmp_buf), H2PacketUnPacker.FRAME_LEN_FLAGS)
                    self.change_state(H2PacketUnPacker.STATE_READ_FLAGS)


            elif self.state == H2PacketUnPacker.STATE_READ_FLAGS:
                if self.read_header_item(buf):
                    self.flags = self.item.get(self.tmp_buf, 0)
                    self.item = H2PacketUnPacker.FrameHeaderItem(len(self.tmp_buf), H2PacketUnPacker.FRAME_LEN_STREAM_IDENTIFIER)
                    self.change_state(H2PacketUnPacker.STATE_READ_STREAM_IDENTIFIER)

            elif self.state == H2PacketUnPacker.STATE_READ_STREAM_IDENTIFIER:
                if self.read_header_item(buf):
                    self.stream_id = \
                        ((self.item.get(self.tmp_buf, 0) & 0x7F) << 24) |  \
                        (self.item.get(self.tmp_buf, 1) << 16) | \
                        (self.item.get(self.tmp_buf, 2) << 8) | \
                        self.item.get(self.tmp_buf, 3)

                    self.item = H2PacketUnPacker.FrameHeaderItem(len(self.tmp_buf), self.payload_len)
                    self.change_state(H2PacketUnPacker.STATE_READ_FLAME_PAYLOAD)


            elif self.state == H2PacketUnPacker.STATE_READ_FLAME_PAYLOAD:
                if self.read_header_item(buf):
                    self.change_state(H2PacketUnPacker.STATE_END)


            else:
                raise RuntimeError("Illegal State")

            if self.state == H2PacketUnPacker.STATE_END:
                pkt = self.pkt_store.rent(self.type)
                pkt.stream_id = self.stream_id
                pkt.flags = H2Flags(self.flags)
                pkt.new_header_accessor().put_bytes(self.tmp_buf.buf, 0, H2Packet.FRAME_HEADER_LEN)
                pkt.new_data_accessor().put_bytes(self.tmp_buf.buf, H2Packet.FRAME_HEADER_LEN,
                                                  len(self.tmp_buf) - H2Packet.FRAME_HEADER_LEN)

                try:
                    next_act = self.cmd_unpacker.packet_received(pkt)
                finally:
                    self.pkt_store.Return(pkt)
                    self.reset_state()

                if next_act == NextSocketAction.SUSPEND:
                    suspend = True
                elif next_act != NextSocketAction.CONTINUE:
                    return next_act

        if suspend:
            return NextSocketAction.SUSPEND
        else:
            return NextSocketAction.CONTINUE


    #
    # private
    #

    def read_header_item(self, buf):
        length = self.item.len - self.item.pos
        if len(buf) - self.pos < length:
            length = len(buf) - self.pos

        self.tmp_buf.put(buf, self.pos, length)
        self.pos += length
        self.item.pos += length

        return self.item.pos == self.item.len

    def change_state(self, new_state):
        self.state = new_state