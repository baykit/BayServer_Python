from bayserver_core.protocol.command_factory import CommandFactory

from bayserver_docker_http.h1.command.cmd_content import CmdContent
from bayserver_docker_http.h1.command.cmd_end_content import CmdEndContent
from bayserver_docker_http.h1.command.cmd_header import CmdHeader
from bayserver_docker_http.h1.h1_type import H1Type


class H1CommandFactory(CommandFactory):

    def create_command(self, type):
        if type == H1Type.HEADER:
            return CmdHeader()
        if type == H1Type.CONTENT:
            return CmdContent()
        if type == H1Type.END_CONTENT:
            return CmdEndContent()
        raise ValueError(f"unknown H1 command type: {type}")
