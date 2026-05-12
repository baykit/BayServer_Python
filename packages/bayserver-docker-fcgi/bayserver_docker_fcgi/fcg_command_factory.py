from bayserver_core.protocol.command_factory import CommandFactory

from bayserver_docker_fcgi.command.cmd_begin_request import CmdBeginRequest
from bayserver_docker_fcgi.command.cmd_end_request import CmdEndRequest
from bayserver_docker_fcgi.command.cmd_params import CmdParams
from bayserver_docker_fcgi.command.cmd_stderr import CmdStdErr
from bayserver_docker_fcgi.command.cmd_stdin import CmdStdIn
from bayserver_docker_fcgi.command.cmd_stdout import CmdStdOut
from bayserver_docker_fcgi.fcg_type import FcgType


class FcgCommandFactory(CommandFactory):

    def create_command(self, type):
        if type == FcgType.BEGIN_REQUEST:
            return CmdBeginRequest()
        if type == FcgType.END_REQUEST:
            return CmdEndRequest()
        if type == FcgType.PARAMS:
            return CmdParams()
        if type == FcgType.STDIN:
            return CmdStdIn()
        if type == FcgType.STDOUT:
            return CmdStdOut()
        if type == FcgType.STDERR:
            return CmdStdErr()
        raise ValueError(f"unknown FCGI command type: {type}")
