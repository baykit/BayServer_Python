from bayserver_core.util.char_util import CharUtil

from bayserver_docker_fcgi.fcg_command import FcgCommand
from bayserver_docker_fcgi.fcg_type import FcgType


#
#  FCGI spec
#    http://www.mit.edu/~yandros/doc/specs/fcgi-spec.html
#
#  Begin request command format
#          typedef struct {
#              unsigned char roleB1;
#              unsigned char roleB0;
#              unsigned char flags;
#              unsigned char reserved[5];
#          } FCGI_BeginRequestBody;
#
class CmdBeginRequest(FcgCommand):
    FCGI_KEEP_CONN = 1
    FCGI_RESPONDER = 1
    FCGI_AUTHORIZER = 2
    FCGI_FILTER = 3

    RESERVED = [CharUtil.SPACE_BYTE] * 5

    def __init__(self, req_id):
        super().__init__(FcgType.BEGIN_REQUEST, req_id)
        self.role = None
        self.keep_conn = None

    def unpack(self, pkt):
        super().unpack(pkt)

        acc = pkt.new_data_accessor()
        self.role = acc.get_short()
        flags = acc.get_byte()
        self.keep_conn = (flags & CmdBeginRequest.FCGI_KEEP_CONN) != 0

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        acc.put_short(self.role)
        acc.put_byte(1 if self.keep_conn else 0)
        acc.put_bytes(CmdBeginRequest.RESERVED)

        # must be called from last line
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_begin_request(self)






