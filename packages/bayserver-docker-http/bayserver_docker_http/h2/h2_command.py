from bayserver_core.protocol.command import Command
from bayserver_docker_http.h2.h2_flags import H2Flags

class H2Command(Command):

    def __init__(self, type, stream_id, flags=None):
        super().__init__(type)
        self.stream_id = stream_id
        if flags is None:
            self.flags = H2Flags()
        else:
            self.flags = flags


    def unpack(self, pkt):
        self.stream_id = pkt.stream_id
        self.flags = pkt.flags


    def pack(self, pkt):
        pkt.stream_id = self.stream_id
        pkt.flags = self.flags
        pkt.pack_header()
