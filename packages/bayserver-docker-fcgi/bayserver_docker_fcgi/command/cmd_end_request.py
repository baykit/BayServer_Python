from bayserver_core.util.char_util import CharUtil

from bayserver_docker_fcgi.fcg_command import FcgCommand
from bayserver_docker_fcgi.fcg_type import FcgType


#
#  FCGI spec
#    http://www.mit.edu/~yandros/doc/specs/fcgi-spec.html
#
#  Endrequest command format
#          typedef struct {
#              unsigned char appStatusB3;
#              unsigned char appStatusB2;
#              unsigned char appStatusB1;
#              unsigned char appStatusB0;
#              unsigned char protocolStatus;
#              unsigned char reserved[3];
#          } FCGI_EndRequestBody;
#

class CmdEndRequest(FcgCommand):
    FCGI_REQUEST_COMPLETE = 0
    FCGI_CANT_MPX_CONN = 1
    FCGI_OVERLOADED = 2
    FCGI_UNKNOWN_ROLE = 3

    RESERVED = [CharUtil.SPACE_BYTE] * 3

    def __init__(self, req_id):
        super().__init__(FcgType.END_REQUEST, req_id)
        self.app_status = 0
        self.protocol_status = CmdEndRequest.FCGI_REQUEST_COMPLETE

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()
        self.app_status = acc.get_int()
        self.protocol_status = acc.get_byte()

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_int(self.app_status)
        acc.put_byte(self.protocol_status)
        acc.put_bytes(CmdEndRequest.RESERVED)

        # must be called from last line
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_end_request(self)