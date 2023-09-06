from bayserver_docker_fcgi.fcg_type import FcgType
from bayserver_docker_fcgi.command.in_out_command_base import InOutCommandBase


#
#  FCGI spec
#    http://www.mit.edu/~yandros/doc/specs/fcgi-spec.html
#
#   StdOut command format
#    raw data
#

class CmdStdOut(InOutCommandBase):
    def __init__(self, req_id, data=None, start=0, length=0):
        super().__init__(FcgType.STDOUT, req_id, data, start, length)

    def handle(self, cmd_handler):
        return cmd_handler.handle_stdout(self)