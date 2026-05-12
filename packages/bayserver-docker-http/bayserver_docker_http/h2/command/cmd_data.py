from bayserver_core.protocol.protocol_exception import ProtocolException

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

    def __init__(self, stream_id=0, flags=None, data=None, start=None, length=None):
        super().__init__(H2Type.DATA, stream_id, flags)
        self.data = data
        self.start = start
        self.length = length

    def init(self, stream_id, flags=None, data=None, start=None, length=None):
        super().init(stream_id, flags)
        self.data = data
        self.start = start
        self.length = length

    def reset(self):
        super().reset()
        self.data = None
        self.start = None
        self.length = None

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()

        pad_length = 0
        if pkt.flags.padded():
            pad_length = acc.get_byte()

        self.data = pkt.buf
        self.start = pkt.header_len + acc.pos
        self.length = pkt.data_len() - acc.pos - pad_length

        # RFC 7540 § 6.1: padding length must leave at least one octet of data.
        if self.length < 0:
            raise ProtocolException(f"DATA pad length exceeds payload: pad={pad_length}")

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        if self.flags.padded():
            raise RuntimeError("Padding not supported")

        acc.put_bytes(self.data, self.start, self.length)
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_data(self)


