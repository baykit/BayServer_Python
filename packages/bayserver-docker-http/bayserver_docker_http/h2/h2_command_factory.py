from bayserver_core.protocol.command_factory import CommandFactory

from bayserver_docker_http.h2.command.cmd_data import CmdData
from bayserver_docker_http.h2.command.cmd_go_away import CmdGoAway
from bayserver_docker_http.h2.command.cmd_headers import CmdHeaders
from bayserver_docker_http.h2.command.cmd_ping import CmdPing
from bayserver_docker_http.h2.command.cmd_preface import CmdPreface
from bayserver_docker_http.h2.command.cmd_priority import CmdPriority
from bayserver_docker_http.h2.command.cmd_rst_stream import CmdRstStream
from bayserver_docker_http.h2.command.cmd_settings import CmdSettings
from bayserver_docker_http.h2.command.cmd_window_update import CmdWindowUpdate
from bayserver_docker_http.h2.h2_type import H2Type


class H2CommandFactory(CommandFactory):

    def create_command(self, type):
        # Python's H2 stack uses CmdHeaders for CONTINUATION too (see
        # H2CommandUnPacker), so route the type through the same class.
        if type == H2Type.DATA:
            return CmdData()
        if type == H2Type.HEADERS or type == H2Type.CONTINUATION:
            return CmdHeaders()
        if type == H2Type.PRIORITY:
            return CmdPriority()
        if type == H2Type.RST_STREAM:
            return CmdRstStream()
        if type == H2Type.SETTINGS:
            return CmdSettings()
        if type == H2Type.PING:
            return CmdPing()
        if type == H2Type.GOAWAY:
            return CmdGoAway()
        if type == H2Type.WINDOW_UPDATE:
            return CmdWindowUpdate()
        if type == H2Type.PREFACE:
            return CmdPreface()
        raise ValueError(f"unknown H2 command type: {type}")
