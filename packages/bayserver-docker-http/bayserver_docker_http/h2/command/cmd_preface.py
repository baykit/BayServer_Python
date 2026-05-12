from bayserver_core.util.string_util import StringUtil

from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type

#
#
#  Preface is dummy command and packet
#
#    packet is not in frame format but raw data: "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"
#

class CmdPreface(H2Command):
    PREFACE_BYTES = "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n".encode("us-ascii")

    def __init__(self, stream_id, flags=None):
        super().__init__(H2Type.PREFACE, stream_id, flags)
        self.protocol = None

    def unpack(self, pkt):
        acc = pkt.new_data_accessor()
        preface_data = bytearray(24)
        acc.get_bytes(preface_data, 0, 24)
        self.protocol = StringUtil.from_bytes(preface_data[6:14])

    def pack(self, pkt):
        # The H2 client connection preface is 24 raw bytes that MUST appear
        # at the very start of the connection — not wrapped in an H2 frame
        # (RFC 7540 § 3.5). H2Packet reserves header_len bytes (9) at the
        # start for the frame header, so the standard new_h2_data_accessor
        # would emit 9 zero bytes before "PRI". Servers misparse the leading
        # zeros as a frame with length=0/type=0, then read "PRI" as the next
        # frame's length and trip MAX_FRAME_SIZE.
        #
        # Bypass the frame-header reserve by writing the preface bytes
        # directly into buf[0..24] and setting buf_len=24.
        preface = CmdPreface.PREFACE_BYTES
        if len(pkt.buf) < len(preface):
            pkt.buf.extend(bytes(len(preface) - len(pkt.buf)))
        pkt.buf[0:len(preface)] = preface
        pkt.buf_len = len(preface)

    def handle(self, cmd_handler):
        return cmd_handler.handle_preface(self)



