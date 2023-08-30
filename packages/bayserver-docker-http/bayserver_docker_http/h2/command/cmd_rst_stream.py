from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type


#
# HTTP/2 RstStream payload format
#
#  +---------------------------------------------------------------+
#  |                        Error Code (32)                        |
#  +---------------------------------------------------------------+
#
#

class CmdRstStream(H2Command):

    def __init__(self, stream_id, flags=None):
        super().__init__(H2Type.RST_STREAM, stream_id, flags)
        self.error_code = None

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()
        self.error_code = acc.get_int()

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_int(self.error_code)
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_rst_stream(self)