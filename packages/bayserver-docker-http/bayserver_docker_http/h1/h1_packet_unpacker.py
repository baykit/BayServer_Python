from bayserver_core.bay_log import BayLog
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.protocol.packet_unpacker import PacketUnPacker
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.simple_buffer import SimpleBuffer
from bayserver_core.util.char_util import CharUtil
from bayserver_docker_http.h1.h1_type import H1Type
from bayserver_docker_http.h1.h1_packet import H1Packet


#    HTTP/1.x has no packet format. So we make HTTP header and content pretend to be packet
#
#    From RFC2616
#    generic-message : start-line
#                      (message-header CRLF)*
#                       CRLF
#                       [message-body]
#
#
#

class H1PacketUnPacker(PacketUnPacker):
    STATE_READ_HEADERS = 1
    STATE_READ_CONTENT = 2
    STATE_END = 3

    MAX_LINE_LEN = 8192

    def __init__(self, cmd_upacker, pkt_store):
        self.cmd_upacker = cmd_upacker
        self.pkt_store = pkt_store
        self.state = None
        self.tmp_buf = SimpleBuffer()
        self.reset_state()

    ######################################################
    # Implements Reusable
    ######################################################
    def reset(self):
        self.reset_state()

    ######################################################
    # Implements PacketUnPacker
    ######################################################
    def bytes_received(self, buf):
        if self.state == H1PacketUnPacker.STATE_END:
            self.reset()
            raise RuntimeError("IllegalState")

        BayLog.debug("H1: bytes_received len=%d", len(buf))

        pos = 0
        buf_start = 0
        line_len = 0
        suspend = False

        if self.state == H1PacketUnPacker.STATE_READ_HEADERS:
            while pos < len(buf):
                b = buf[pos]
                self.tmp_buf.put_byte(b)
                pos += 1
                if b == CharUtil.CR_BYTE:
                    next
                elif b == CharUtil.LF_BYTE:
                    if line_len == 0:
                        # empty line (all headers are read)
                        pkt = self.pkt_store.rent(H1Type.HEADER)
                        pkt.new_data_accessor().put_bytes(self.tmp_buf.byte_data(), 0, self.tmp_buf.length)
                        upgrade = False
                        try:
                            next_act = self.cmd_upacker.packet_received(pkt)
                        finally:
                            self.pkt_store.Return(pkt)

                        if next_act == NextSocketAction.CONTINUE or next_act == NextSocketAction.SUSPEND:
                            if self.cmd_upacker.req_finished():
                                self.change_state(H1PacketUnPacker.STATE_END)
                            else:
                                self.change_state(H1PacketUnPacker.STATE_READ_CONTENT)

                        elif next_act == NextSocketAction.CLOSE:
                            # Maybe error
                            self.reset_state()
                            return next_act

                        else:
                            raise RuntimeError(f"Invalid next action: {next_act}")

                        suspend = (next_act == NextSocketAction.SUSPEND)
                        break

                    line_len = 0
                else:
                    line_len += 1

                if line_len >= H1PacketUnPacker.MAX_LINE_LEN:
                    raise ProtocolException("Http/1 Line is too long")

        if self.state == H1PacketUnPacker.STATE_READ_CONTENT:
            while pos < len(buf):
                pkt = self.pkt_store.rent(H1Type.CONTENT)

                length = len(buf) - pos
                if length > H1Packet.MAX_DATA_LEN:
                    length = H1Packet.MAX_DATA_LEN

                pkt.new_data_accessor().put_bytes(buf, pos, length)
                pos += length

                try:
                    next_act = self.cmd_upacker.packet_received(pkt)
                finally:
                    self.pkt_store.Return(pkt)

                if next_act == NextSocketAction.CONTINUE or \
                        next_act == NextSocketAction.WRITE:
                    if self.cmd_upacker.req_finished():
                        self.change_state(H1PacketUnPacker.STATE_END)
                elif next_act == NextSocketAction.SUSPEND:
                    suspend = True
                elif next_act == NextSocketAction.CLOSE:
                    self.reset_state()
                    return next_act

        if self.state == H1PacketUnPacker.STATE_END:
            self.reset_state()


        if suspend:
            BayLog.debug("H1 read suspend")
            return NextSocketAction.SUSPEND
        else:
            return NextSocketAction.CONTINUE


    def change_state(self, new_state):
        self.state = new_state

    def reset_state(self):
        self.change_state(H1PacketUnPacker.STATE_READ_HEADERS)
        self.tmp_buf.reset()

