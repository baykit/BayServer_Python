from baykit.bayserver.docker.warp.warp_handler import WarpHandler

from baykit.bayserver.protocol.protocol_handler_factory import ProtocolHandlerFactory

from baykit.bayserver.docker.http.h2.h2_command_handler import H2CommandHandler
from baykit.bayserver.docker.http.h2.h2_protocol_handler import H2ProtocolHandler

class H2WarpHandler(H2CommandHandler, WarpHandler):

    class WarpProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            cmd_hnd = H2WarpHandler()
            proto_hnd = H2ProtocolHandler.new_handler(pkt_store, cmd_hnd, False)
            cmd_hnd.set_protocol_handler(proto_hnd)
            return proto_hnd


    def verify_protocol(self, proto):
        pass