from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.sink import Sink
from baykit.bayserver.protocol.command_unpacker import CommandUnPacker

from baykit.bayserver.docker.ajp.ajp_type import AjpType
from baykit.bayserver.docker.ajp.command.cmd_data import CmdData
from baykit.bayserver.docker.ajp.command.cmd_end_response import CmdEndResponse
from baykit.bayserver.docker.ajp.command.cmd_forward_request import CmdForwardRequest
from baykit.bayserver.docker.ajp.command.cmd_get_body_chunk import CmdGetBodyChunk
from baykit.bayserver.docker.ajp.command.cmd_send_body_chunk import CmdSendBodyChunk
from baykit.bayserver.docker.ajp.command.cmd_send_headers import CmdSendHeaders
from baykit.bayserver.docker.ajp.command.cmd_shutdown import CmdShutdown

class AjpCommandUnPacker(CommandUnPacker):

    def __init__(self, handler):
        self.cmd_handler = handler
        self.reset()

    def reset(self):
        pass

    def packet_received(self, pkt):

        BayLog.debug("ajp:  packet received: type=%d data len=%d", pkt.type, pkt.data_len())

        if pkt.type == AjpType.DATA:
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

        cmd.unpack(pkt)
        return cmd.handle(self.cmd_handler)  # visit

    def need_data(self):
        return self.cmd_handler.need_data()
