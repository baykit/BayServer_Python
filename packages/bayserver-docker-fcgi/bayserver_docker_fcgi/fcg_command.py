from bayserver_core.protocol.command import Command

class FcgCommand(Command):

    def __init__(self, typ, req_id):
        super().__init__(typ)
        self.req_id = req_id

    def unpack(self, pkt):
        self.req_id = pkt.req_id

    #
    # Super class method must be called from last line of override method
    # since header cannot be packed before data is constructed
    #
    def pack(self, pkt):
        pkt.req_id = self.req_id
        self.pack_header(pkt)

    def pack_header(self, pkt):
        acc = pkt.new_header_accessor()
        acc.put_byte(pkt.version)
        acc.put_byte(pkt.type)
        acc.put_short(pkt.req_id)
        acc.put_short(pkt.data_len())
        acc.put_byte(0)  # paddinglen
        acc.put_byte(0)  # reserved


