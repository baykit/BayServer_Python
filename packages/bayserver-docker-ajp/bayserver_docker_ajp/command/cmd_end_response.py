from bayserver_docker_ajp.ajp_command import AjpCommand
from bayserver_docker_ajp.ajp_type import AjpType


#
#  End response body format
#
#  AJP13_END_RESPONSE :=
#    prefix_code       5
#    reuse             (boolean)
#

class CmdEndResponse(AjpCommand):

    def __init__(self):
        super().__init__(AjpType.END_RESPONSE, False)
        self.reuse = None

    def pack(self, pkt):
        acc = pkt.new_ajp_data_accessor()
        acc.put_byte(self.type)
        acc.put_byte(1 if self.reuse else 0)

        #  must be called from last line
        super().pack(pkt)

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_ajp_data_accessor()
        acc.get_byte()  # prefix code
        self.reuse = acc.get_byte() != 0


    def handle(self, handler):
        return handler.handle_end_response(self)
