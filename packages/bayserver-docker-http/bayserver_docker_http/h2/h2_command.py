from bayserver_core.protocol.command import Command
from bayserver_docker_http.h2.h2_flags import H2Flags

class H2Command(Command):

    def __init__(self, type, stream_id=0, flags=None):
        super().__init__(type)
        self.stream_id = stream_id
        if flags is None:
            self.flags = H2Flags()
        else:
            self.flags = flags

    def init(self, stream_id, flags=None):
        """Re-initialise a pooled H2 command for the next rental."""
        self.stream_id = stream_id
        if flags is None:
            self.flags = H2Flags()
        else:
            self.flags = flags

    def reset(self):
        # Subclasses override and call super().reset() to clear per-frame
        # fields. Pool identity (= the H2 type tag) is preserved.
        self.stream_id = 0
        self.flags = H2Flags()

    def unpack(self, pkt):
        self.stream_id = pkt.stream_id
        self.flags = pkt.flags


    def pack(self, pkt):
        pkt.stream_id = self.stream_id
        pkt.flags = self.flags
        pkt.pack_header()
