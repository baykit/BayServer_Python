from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.protocol.command_unpacker import CommandUnPacker


from bayserver_docker_http.h1.h1_type import H1Type
from bayserver_docker_http.h1.command.cmd_header import CmdHeader
from bayserver_docker_http.h1.command.cmd_content import CmdContent


class H1CommandUnPacker(CommandUnPacker):

    def __init__(self, cmd_handler, svr_mode):
        self.cmd_handler = cmd_handler
        self.server_mode = svr_mode

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        pass

    ######################################################
    # Implements CommandUnpacker
    ######################################################

    def packet_received(self, pkt):
        BayLog.debug("h1: read packet type=%d length=%d", pkt.type, pkt.data_len())

        if pkt.type == H1Type.HEADER:
            cmd = CmdHeader(self.server_mode)
        elif pkt.type == H1Type.CONTENT:
            cmd = CmdContent()
        else:
            self.reset()
            raise Sink("IllegalState")

        cmd.unpack(pkt)
        return cmd.handle(self.cmd_handler)


    def req_finished(self):
        return self.cmd_handler.req_finished()