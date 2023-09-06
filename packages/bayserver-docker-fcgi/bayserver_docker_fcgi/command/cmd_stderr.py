
from bayserver_docker_fcgi.fcg_type import FcgType
from bayserver_docker_fcgi.command.in_out_command_base import InOutCommandBase

#
#  FCGI spec
#    http://www.mit.edu/~yandros/doc/specs/fcgi-spec.html
#
#   StdErr command format
#    raw data
#

class CmdStdErr(InOutCommandBase):

    def __init__(self, req_id):
        super().__init__(FcgType.STDERR, req_id)

    def handle(self, cmd_handler):
        return cmd_handler.handle_stderr(self)

