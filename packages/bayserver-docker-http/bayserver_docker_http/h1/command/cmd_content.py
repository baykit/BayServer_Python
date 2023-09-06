from bayserver_docker_http.h1.h1_command import H1Command
from bayserver_docker_http.h1.h1_type import H1Type


class CmdContent(H1Command):
    def __init__(self, buf=None, start=None, length=None):
        H1Command.__init__(self, H1Type.CONTENT)
        self.buf = buf
        self.start = start
        self.length = length

    def unpack(self, pkt):
        self.buf = pkt.buf
        self.start = pkt.header_len
        self.length = pkt.data_len()

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_bytes(self.buf, self.start, self.length)

    def handle(self, cmd_handler):
        return cmd_handler.handle_content(self)
