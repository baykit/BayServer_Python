from bayserver_docker_ajp.ajp_command import AjpCommand
from bayserver_docker_ajp.ajp_type import AjpType

#
#  Shutdown command format
#
#    none
#

class CmdShutdown(AjpCommand):

    def __init__(self):
        # Note: was previously super(AjpType.SHUTDOWN, True) which
        # silently became a no-op (super() with args returns a proxy
        # but never called __init__). Pre-existing bug; corrected here
        # as part of the pool migration so a pooled CmdShutdown is in
        # the correct state.
        super().__init__(AjpType.SHUTDOWN, True)

    def init(self):
        pass

    def reset(self):
        pass

    def unpack(self, pkt):
        super().unpack(pkt)

    def pack(self, pkt):
        super().pack(pkt)

    def handle(self, handler):
        return handler.handle_shutdown(self)
