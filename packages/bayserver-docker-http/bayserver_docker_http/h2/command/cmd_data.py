from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type

#
# HTTP/2 Data payload format
#
# +---------------+
# |Pad Length? (8)|
# +---------------+-----------------------------------------------+
# |                            Data (*)                         ...
# +---------------------------------------------------------------+
# |                           Padding (*)                       ...
# +---------------------------------------------------------------+
#

class CmdData(H2Command):

    def __init__(self, stream_id, flags, data=None, start=None, length=None):
        super().__init__(H2Type.DATA, stream_id, flags)
        self.data = data
        self.start = start
        self.length = length

    def unpack(self, pkt):
        super().unpack(pkt)
        self.data = pkt.buf
        self.start = pkt.header_len
        self.length = pkt.data_len()

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        if self.flags.padded():
            raise RuntimeError("Padding not supported")

        acc.put_bytes(self.data, self.start, self.length)
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_data(self)


