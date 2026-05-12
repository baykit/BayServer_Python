from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.protocol.command_unpacker import CommandUnPacker


from bayserver_docker_http.h1.h1_type import H1Type
from bayserver_docker_http.h1.command.cmd_header import CmdHeader
from bayserver_docker_http.h1.command.cmd_content import CmdContent


class H1CommandUnPacker(CommandUnPacker):

    def __init__(self, cmd_handler, svr_mode, cmd_store=None):
        self.cmd_handler = cmd_handler
        self.server_mode = svr_mode
        # Per-agent Command pool (optional). When supplied, packet_received
        # rents a pooled Command and returns it after handle() runs;
        # otherwise it allocates a fresh Command per packet.
        self.cmd_store = cmd_store

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
            if self.cmd_store is not None:
                cmd = self.cmd_store.rent(pkt.type)
                cmd.init(self.server_mode)
            else:
                cmd = CmdHeader(self.server_mode)
        elif pkt.type == H1Type.CONTENT:
            if self.cmd_store is not None:
                cmd = self.cmd_store.rent(pkt.type)
            else:
                cmd = CmdContent()
        else:
            self.reset()
            raise Sink("IllegalState")

        try:
            cmd.unpack(pkt)
            return cmd.handle(self.cmd_handler)
        finally:
            if self.cmd_store is not None:
                self.cmd_store.Return(cmd)


    def req_finished(self):
        return self.cmd_handler.req_finished()
