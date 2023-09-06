from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.protocol_exception import ProtocolException

from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type


#
#  HTTP/2 Setting payload format
#
#  +-------------------------------+
#  |       Identifier (16)         |
#  +-------------------------------+-------------------------------+
#  |                        Value (32)                             |
#  +---------------------------------------------------------------+
#
#

class CmdSettings(H2Command):

    class Item:

        def __init__(self, id, value):
            self.id = id
            self.value = value

    HEADER_TABLE_SIZE = 0x1
    ENABLE_PUSH = 0x2
    MAX_CONCURRENT_STREAMS = 0x3
    INITIAL_WINDOW_SIZE = 0x4
    MAX_FRAME_SIZE = 0x5
    MAX_HEADER_LIST_SIZE = 0x6

    INIT_HEADER_TABLE_SIZE = 4096
    INIT_ENABLE_PUSH = 1
    INIT_MAX_CONCURRENT_STREAMS = -1
    INIT_INITIAL_WINDOW_SIZE = 65535
    INIT_MAX_FRAME_SIZE = 16384
    INIT_MAX_HEADER_LIST_SIZE = -1

    def __init__(self, stream_id, flags=None):
        super().__init__(H2Type.SETTINGS, stream_id, flags)
        self.items = []

    def unpack(self, pkt):
        super().unpack(pkt)
        if self.flags.ack():
            return

        acc = pkt.new_data_accessor()
        pos = 0
        while pos < pkt.data_len():
            id = acc.get_short()
            value = acc.get_int()
            self.items.append(CmdSettings.Item(id, value))
            pos += 6

    def pack(self, pkt):
        if self.flags.ack():
            # do not pack payload
            pass
        else:
            acc = pkt.new_data_accessor()
            for item in self.items:
                acc.put_short(item.id)
                acc.put_int(item.value)

        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_settings(self)
