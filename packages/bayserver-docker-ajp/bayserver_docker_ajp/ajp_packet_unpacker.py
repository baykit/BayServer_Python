from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.packet_unpacker import PacketUnPacker

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.util.simple_buffer import SimpleBuffer
from bayserver_core.util.char_util import CharUtil

from bayserver_docker_ajp.ajp_packet import AjpPacket
from bayserver_docker_ajp.ajp_type import AjpType

class AjpPacketUnPacker(PacketUnPacker):
    STATE_READ_PREAMBLE = 1
    STATE_READ_BODY = 2
    STATE_END = 3

    def __init__(self, pkt_store, cmd_unpacker):

        self.preamble_buf = None
        self.body_buf = None
    
        self.state = None
    
        self.body_len = None
        self.read_bytes = None
        self.type = None
        self.to_server = None
        self.need_data = None
        self.pkt_store = pkt_store
        self.cmd_unpacker = cmd_unpacker
        self.preamble_buf = SimpleBuffer()
        self.body_buf = SimpleBuffer()
        self.reset()

    def reset(self):
        self.state = AjpPacketUnPacker.STATE_READ_PREAMBLE
        self.body_len = 0
        self.read_bytes = 0
        self.need_data = False
        self.preamble_buf.reset()
        self.body_buf.reset()

    def bytes_received(self, buf):
        suspend = False
        pos = 0

        while pos < len(buf):
            if self.state == AjpPacketUnPacker.STATE_READ_PREAMBLE:
                length = AjpPacket.PREAMBLE_SIZE - len(self.preamble_buf)
                if len(buf) - pos < length:
                    length = len(buf) - pos

                self.preamble_buf.put(buf, pos, length)
                pos += length

                if len(self.preamble_buf) == AjpPacket.PREAMBLE_SIZE:
                    self.preamble_read()
                    self.change_state(AjpPacketUnPacker.STATE_READ_BODY)

            if self.state == AjpPacketUnPacker.STATE_READ_BODY:
                length = self.body_len - len(self.body_buf)
                if length > len(buf) - pos:
                    length = len(buf) - pos

                self.body_buf.put(buf, pos, length)
                pos += length

                if len(self.body_buf) == self.body_len:
                    self.body_read()
                    self.change_state(AjpPacketUnPacker.STATE_END)

            if self.state == AjpPacketUnPacker.STATE_END:

                pkt = self.pkt_store.rent(self.type)
                pkt.to_server = self.to_server
                pkt.new_ajp_header_accessor().put_bytes(self.preamble_buf.buf, 0, len(self.preamble_buf))
                pkt.new_ajp_data_accessor().put_bytes(self.body_buf.buf, 0, len(self.body_buf))

                try:
                    next_action = self.cmd_unpacker.packet_received(pkt)
                finally:
                    self.pkt_store.Return(pkt)

                self.reset()
                self.need_data = self.cmd_unpacker.need_data()

                if next_action == NextSocketAction.SUSPEND:
                    suspend = True
                elif next_action != NextSocketAction.CONTINUE:
                    return next_action

        BayLog.debug("ajp next read")
        if suspend:
            return NextSocketAction.SUSPEND
        else:
            return NextSocketAction.CONTINUE

    def change_state(self, new_state):
        self.state = new_state

    def preamble_read(self):
        data = self.preamble_buf.buf

        if data[0] == 0x12 and data[1] == 0x34:
            self.to_server = True
        elif data[0] == CharUtil.A_BYTE and data[1] == CharUtil.B_BYTE:
            self.to_server = False

        else:
            raise RuntimeError("Must be start with 0x1234 or 'AB'")


        self.body_len = ((data[2] << 8) | (data[3] & 0xff)) & 0xffff
        BayLog.trace("ajp: read packet preamble: bodyLen=%d", self.body_len)

    def body_read(self):
        if self.need_data:
            self.type = AjpType.DATA
        else:
            self.type = self.body_buf.buf[0] & 0xff