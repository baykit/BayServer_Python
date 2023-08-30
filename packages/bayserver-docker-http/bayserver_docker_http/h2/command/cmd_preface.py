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
        acc = pkt.new_h2_data_accessor()
        acc.put_bytes(CmdPreface.PREFACE_BYTES)

    def handle(self, cmd_handler):
        return cmd_handler.handle_preface(self)



