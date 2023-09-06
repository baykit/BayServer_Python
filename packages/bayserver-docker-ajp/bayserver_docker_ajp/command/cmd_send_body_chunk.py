from bayserver_docker_ajp.ajp_command import AjpCommand
from bayserver_docker_ajp.ajp_packet import AjpPacket
from bayserver_docker_ajp.ajp_type import AjpType

#
#  Send body chunk format
#
#  AJP13_SEND_BODY_CHUNK :=
#    prefix_code   (byte) 0x03
#    chunk_length  (integer)
#    chunk         *(byte)
#

class CmdSendBodyChunk(AjpCommand):

    MAX_CHUNKLEN = AjpPacket.MAX_DATA_LEN - 4

    def __init__(self, buf, ofs, length):
        super().__init__(AjpType.SEND_BODY_CHUNK, False)
        self.chunk = buf
        self.offset = ofs
        self.length = length

    def pack(self, pkt):
        if self.length > CmdSendBodyChunk.MAX_CHUNKLEN:
            raise RuntimeError("IllegalArgument")

        acc = pkt.new_ajp_data_accessor()
        acc.put_byte(self.type)
        acc.put_short(self.length)
        acc.put_bytes(self.chunk, self.offset, self.length)
        acc.put_byte(0)  # maybe document bug

        #  must be called from last line
        super().pack(pkt)

    def unpack(self, pkt):
        acc = pkt.new_ajp_data_accessor()
        acc.get_byte()  # code
        self.length = acc.get_short()
        if self.chunk is None or self.length > len(self.chunk):
            self.chunk = bytearray(self.length)

        acc.get_bytes(self.chunk, 0, self.length)

    def handle(self, handler):
        return handler.handle_send_body_chunk(self)