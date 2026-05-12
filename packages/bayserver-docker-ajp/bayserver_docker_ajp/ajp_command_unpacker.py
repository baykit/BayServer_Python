from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.protocol.command_unpacker import CommandUnPacker

from bayserver_docker_ajp.ajp_type import AjpType
from bayserver_docker_ajp.command.cmd_data import CmdData
from bayserver_docker_ajp.command.cmd_end_response import CmdEndResponse
from bayserver_docker_ajp.command.cmd_forward_request import CmdForwardRequest
from bayserver_docker_ajp.command.cmd_get_body_chunk import CmdGetBodyChunk
from bayserver_docker_ajp.command.cmd_send_body_chunk import CmdSendBodyChunk
from bayserver_docker_ajp.command.cmd_send_headers import CmdSendHeaders
from bayserver_docker_ajp.command.cmd_shutdown import CmdShutdown

class AjpCommandUnPacker(CommandUnPacker):

    def __init__(self, handler, cmd_store=None):
        self.cmd_handler = handler
        # Per-agent Command pool (optional). When supplied, packet_received
        # rents a pooled Command and Returns it after handle() runs.
        self.cmd_store = cmd_store
        self.reset()

    def reset(self):
        pass

    def packet_received(self, pkt):

        BayLog.debug("ajp:  packet received: type=%d data len=%d", pkt.type, pkt.data_len())

        if self.cmd_store is not None:
            cmd = self.cmd_store.rent(pkt.type)
            cmd.init()
        elif pkt.type == AjpType.DATA:
            cmd = CmdData()
        elif pkt.type == AjpType.FORWARD_REQUEST:
            cmd = CmdForwardRequest()
        elif pkt.type == AjpType.SEND_BODY_CHUNK:
            cmd = CmdSendBodyChunk(pkt.buf, pkt.header_len, pkt.data_len)
        elif pkt.type == AjpType.SEND_HEADERS:
            cmd = CmdSendHeaders()
        elif pkt.type == AjpType.END_RESPONSE:
            cmd = CmdEndResponse()
        elif pkt.type == AjpType.SHUTDOWN:
            cmd = CmdShutdown()
        elif pkt.type == AjpType.GET_BODY_CHUNK:
            cmd = CmdGetBodyChunk()
        else:
            raise Sink()

        try:
            cmd.unpack(pkt)
            return cmd.handle(self.cmd_handler)
        finally:
            if self.cmd_store is not None:
                self.cmd_store.Return(cmd)

    def need_data(self):
        return self.cmd_handler.need_data()
