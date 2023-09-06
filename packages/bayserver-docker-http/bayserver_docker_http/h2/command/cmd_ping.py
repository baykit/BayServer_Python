from bayserver_docker_http.h2.h2_command import H2Command
from bayserver_docker_http.h2.h2_type import H2Type


class CmdPing(H2Command):

    def __init__(self, stream_id, flags=None, opaque_data=None):
        super().__init__(H2Type.PING, stream_id, flags)
        if opaque_data is None:
            self.opaque_data = bytearray(8)
        else:
            self.opaque_data = opaque_data

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()

        acc.get_bytes(self.opaque_data, 0, 8)

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_bytes(self.opaque_data)
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_ping(self)

