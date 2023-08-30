from bayserver_core.protocol.command_unpacker import CommandUnPacker

from bayserver_docker_fcgi.fcg_type import FcgType
from bayserver_docker_fcgi.command.cmd_begin_request import CmdBeginRequest
from bayserver_docker_fcgi.command.cmd_end_request import CmdEndRequest
from bayserver_docker_fcgi.command.cmd_params import CmdParams
from bayserver_docker_fcgi.command.cmd_stdin import CmdStdIn
from bayserver_docker_fcgi.command.cmd_stdout import CmdStdOut
from bayserver_docker_fcgi.command.cmd_stderr import CmdStdErr

class FcgCommandUnPacker(CommandUnPacker):

    def __init__(self, handler):
        self.handler = handler
        self.reset()

    def reset(self):
        pass

    def packet_received(self, pkt):

        if pkt.type == FcgType.BEGIN_REQUEST:
            cmd = CmdBeginRequest(pkt.req_id)

        elif pkt.type == FcgType.END_REQUEST:
            cmd = CmdEndRequest(pkt.req_id)

        elif pkt.type == FcgType.PARAMS:
            cmd = CmdParams(pkt.req_id)

        elif pkt.type == FcgType.STDIN:
            cmd = CmdStdIn(pkt.req_id)

        elif pkt.type == FcgType.STDOUT:
            cmd = CmdStdOut(pkt.req_id)

        elif pkt.type == FcgType.STDERR:
            cmd = CmdStdErr(pkt.req_id)

        else:
            raise RuntimeError("IllegalState")

        cmd.unpack(pkt)
        cmd.handle(self.handler)