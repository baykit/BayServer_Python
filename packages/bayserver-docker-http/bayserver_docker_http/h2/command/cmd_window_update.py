from bayserver_core.bay_log import BayLog

from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_packet import H2Packet

#
#  HTTP/2 Window Update payload format
#
#  +-+-------------------------------------------------------------+
#  |R|              Window Size Increment (31)                     |
#  +-+-------------------------------------------------------------+
#

class CmdWindowUpdate(H2Command):

    def __init__(self, stream_id, flags=None):
        super().__init__(H2Type.WINDOW_UPDATE, stream_id, flags)
        self.items = []
        self.window_size_increment = None

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()
        val = acc.get_int()
        self.window_size_increment = H2Packet.extract_int31(val)

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_int(H2Packet.consolidate_flag_and_int32(0, self.window_size_increment))
        BayLog.trace("h2: Pack windowUpdate size=%d", self.window_size_increment)
        super().pack(pkt)

    def handle(self ,cmd_handler):
        return cmd_handler.handle_window_update(self)
