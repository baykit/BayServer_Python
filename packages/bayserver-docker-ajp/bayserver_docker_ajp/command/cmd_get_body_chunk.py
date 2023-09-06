from bayserver_docker_ajp.ajp_command import AjpCommand
from bayserver_docker_ajp.ajp_type import AjpType

#
# Get Body Chunk format
#
# AJP13_GET_BODY_CHUNK :=
#   prefix_code       6
#   requested_length  (integer)
#

class CmdGetBodyChunk(AjpCommand):

    def __init__(self):
        super().__init__(AjpType.GET_BODY_CHUNK, False)
        self.req_len = None

    def pack(self, pkt):
        acc = pkt.new_ajp_data_accessor()
        acc.put_byte(self.type)
        acc.put_short(self.req_len)

        # must be called from last line
        super().pack(pkt)

    def handle(self, handler):
        return handler.handle_get_body_chunk(self)
