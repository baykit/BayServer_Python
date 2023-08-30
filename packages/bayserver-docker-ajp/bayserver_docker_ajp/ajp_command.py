from bayserver_core.protocol.command import Command
from bayserver_core.util.char_util import CharUtil

class AjpCommand(Command):

    def __init__(self, typ, to_server):
        super().__init__(typ)
        self.to_server = to_server

    def unpack(self, pkt):
        if pkt.type != self.type:
            raise RuntimeError("Illegal State")

        self.to_server = pkt.to_server

    #
    # Super class method must be called from last line of override method
    # since header cannot be packed before data is constructed.
    #
    def pack(self, pkt):
        if pkt.type != self.type:
            raise RuntimeError("Illegal State")

        pkt.to_server = self.to_server
        self.pack_header(pkt)

    def pack_header(self, pkt):
        acc = pkt.new_ajp_header_accessor()
        if pkt.to_server:
            acc.put_byte(0x12)
            acc.put_byte(0x34)
        else:
            acc.put_byte(CharUtil.A_BYTE)
            acc.put_byte(CharUtil.B_BYTE)

        acc.put_byte((pkt.data_len() >> 8) & 0xff)
        acc.put_byte(pkt.data_len() & 0xff)
