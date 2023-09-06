from bayserver_core.util.string_util import StringUtil

from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_packet import H2Packet

#
#  HTTP/2 GoAway payload format
#
#  +-+-------------------------------------------------------------+
#  |R|                  Last-Stream-ID (31)                        |
#  +-+-------------------------------------------------------------+
#  |                      Error Code (32)                          |
#  +---------------------------------------------------------------+
#  |                  Additional Debug Data (*)                    |
#  +---------------------------------------------------------------+
#
#

class CmdGoAway(H2Command):

    def __init__(self, stream_id, flags=None):
        super().__init__(H2Type.GOAWAY, stream_id, flags)
        self.last_stream_id = None
        self.error_code = None
        self.debug_data = None

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()
        val = acc.get_int()
        self.last_stream_id = H2Packet.extract_int31(val)
        self.error_code = acc.get_int()
        self.debug_data = bytearray(pkt.data_len() - acc.pos)
        acc.get_bytes(self.debug_data, 0, len(self.debug_data))

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_int(self.last_stream_id)
        acc.put_int(self.error_code)
        if self.debug_data:
            acc.put_bytes(self.debug_data, 0, len(self.debug_data))
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_go_away(self)