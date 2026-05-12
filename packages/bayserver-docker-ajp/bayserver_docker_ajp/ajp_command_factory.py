from bayserver_core.protocol.command_factory import CommandFactory

from bayserver_docker_ajp.ajp_type import AjpType
from bayserver_docker_ajp.command.cmd_data import CmdData
from bayserver_docker_ajp.command.cmd_end_response import CmdEndResponse
from bayserver_docker_ajp.command.cmd_forward_request import CmdForwardRequest
from bayserver_docker_ajp.command.cmd_get_body_chunk import CmdGetBodyChunk
from bayserver_docker_ajp.command.cmd_send_body_chunk import CmdSendBodyChunk
from bayserver_docker_ajp.command.cmd_send_headers import CmdSendHeaders
from bayserver_docker_ajp.command.cmd_shutdown import CmdShutdown


class AjpCommandFactory(CommandFactory):

    def create_command(self, type):
        if type == AjpType.DATA:
            return CmdData()
        if type == AjpType.FORWARD_REQUEST:
            return CmdForwardRequest()
        if type == AjpType.SEND_BODY_CHUNK:
            return CmdSendBodyChunk()
        if type == AjpType.SEND_HEADERS:
            return CmdSendHeaders()
        if type == AjpType.END_RESPONSE:
            return CmdEndResponse()
        if type == AjpType.GET_BODY_CHUNK:
            return CmdGetBodyChunk()
        if type == AjpType.SHUTDOWN:
            return CmdShutdown()
        raise ValueError(f"unknown AJP command type: {type}")
