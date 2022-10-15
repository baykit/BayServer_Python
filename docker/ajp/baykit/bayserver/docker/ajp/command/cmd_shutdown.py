from baykit.bayserver.docker.ajp.ajp_command import AjpCommand
from baykit.bayserver.docker.ajp.ajp_type import AjpType

#
#  Shutdown command format
#
#    none
#

class CmdShutdown(AjpCommand):

    def __init__(self):
        super(AjpType.SHUTDOWN, True)

    def unpack(self, pkt):
        super().unpack(pkt)

    def pack(self, pkt):
        super().pack(pkt)

    def handle(self, handler):
        return handler.handle_shutdown(self)
