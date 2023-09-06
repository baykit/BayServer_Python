from bayserver_docker_http.h1.h1_command import H1Command
from bayserver_docker_http.h1.h1_type import H1Type

# Dummy command
class CmdEndContent(H1Command):

    def __init__(self):
        H1Command.__init__(self, H1Type.END_CONTENT)

    def unpack(self, pkt):
        pass

    def pack(self, pkt):
        pass

    def handle(self, cmd_handler):
        return cmd_handler.handle_end_content(self)

