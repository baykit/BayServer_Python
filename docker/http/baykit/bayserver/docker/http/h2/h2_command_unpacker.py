from baykit.bayserver.bay_log import BayLog

from baykit.bayserver.protocol.command_unpacker import CommandUnPacker

from baykit.bayserver.docker.http.h2.h2_type import H2Type
from baykit.bayserver.docker.http.h2.command.cmd_data import CmdData
from baykit.bayserver.docker.http.h2.command.cmd_go_away import CmdGoAway
from baykit.bayserver.docker.http.h2.command.cmd_headers import CmdHeaders
from baykit.bayserver.docker.http.h2.command.cmd_ping import CmdPing
from baykit.bayserver.docker.http.h2.command.cmd_preface import CmdPreface
from baykit.bayserver.docker.http.h2.command.cmd_priority import CmdPriority
from baykit.bayserver.docker.http.h2.command.cmd_rst_stream import CmdRstStream
from baykit.bayserver.docker.http.h2.command.cmd_settings import CmdSettings
from baykit.bayserver.docker.http.h2.command.cmd_window_update import CmdWindowUpdate

class H2CommandUnPacker(CommandUnPacker):

    def __init__(self, cmd_handler):
        self.cmd_handler = cmd_handler

    def reset(self):
        pass

    def packet_received(self, pkt):
        BayLog.debug("h2: read packet type=%d strmid=%d len=%d flgs=%s",
                     pkt.type, pkt.stream_id, pkt.data_len(), pkt.flags)

        if pkt.type == H2Type.PREFACE:
            cmd = CmdPreface(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.HEADERS:
            cmd = CmdHeaders(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.PRIORITY:
            cmd = CmdPriority(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.SETTINGS:
            cmd = CmdSettings(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.WINDOW_UPDATE:
            cmd = CmdWindowUpdate(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.DATA:
            cmd = CmdData(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.GOAWAY:
            cmd = CmdGoAway(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.PING:
            cmd = CmdPing(pkt.stream_id, pkt.flags)

        elif pkt.type == H2Type.RST_STREAM:
            cmd = CmdRstStream(pkt.stream_id, pkt.flags)

        else:
            self.reset()
            raise RuntimeError(f"Invalid Packet: {pkt}")

        cmd.unpack(pkt)
        return cmd.handle(self.cmd_handler)