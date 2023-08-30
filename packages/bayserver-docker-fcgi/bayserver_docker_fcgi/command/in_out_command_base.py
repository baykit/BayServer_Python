
from bayserver_docker_fcgi.fcg_command import FcgCommand


class InOutCommandBase(FcgCommand):

    def __init__(self, typ, req_id, data=None, start=0, length=0):
        super().__init__(typ, req_id)
        self.data = data
        self.start = start
        self.length = length

    def unpack(self, pkt):
        super().unpack(pkt)
        self.start = pkt.header_len
        self.length = pkt.data_len()
        self.data = pkt.buf

    def pack(self, pkt):
        if self.data is not None and self.length > 0:
            acc = pkt.new_data_accessor()
            acc.put_bytes(self.data, self.start, self.length)

        # must be called from last line
        super().pack(pkt)
