from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type
from bayserver_docker_http.h2.h2_packet import H2Packet

#
# HTTP/2 Priority payload format
#
#  +-+-------------------------------------------------------------+
#  |E|                  Stream Dependency (31)                     |
#  +-+-------------+-----------------------------------------------+
#  |   Weight (8)  |
#  +-+-------------+
#
#
class CmdPriority(H2Command):

    def __init__(self, stream_id, flags=None):
        super().__init__(H2Type.PRIORITY, stream_id, flags)
        self.weight = None
        self.excluded = None
        self.stream_dependency = None

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()

        val = acc.get_int()
        self.excluded = H2Packet.extract_flag(val) == 1
        self.stream_dependency = H2Packet.extract_int31(val)
        self.weight = acc.get_byte()

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_int(H2Packet.make_stream_depency32(self.excluded, self.stream_dependency))
        acc.put_byte(self.weight)
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_priority(self)