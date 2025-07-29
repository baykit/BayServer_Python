from typing import List

from bayserver_core.common.inbound_handler import InboundHandler
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.protocol.protocol_handler_factory import ProtocolHandlerFactory
from bayserver_core.sink import Sink
from bayserver_docker_http3.qic_handler import QicHandler
from bayserver_docker_http3.qic_protocol_handler import QicProtocolHandler


class QicInboundHandler(QicHandler, InboundHandler):

    class InboundProtocolHandlerFactory(ProtocolHandlerFactory):

        def create_protocol_handler(self, pkt_store):
            ib_handler = QicInboundHandler()
            pkt_unpacker = None
            pkt_packer = None
            cmd_packer = None

            proto_handler = QicProtocolHandler(ib_handler, pkt_unpacker, pkt_packer, None, cmd_packer, True)
            ib_handler.init(proto_handler)
            return proto_handler

    protocol_handler: QicProtocolHandler = None

    def __init__(self):
        self.reset()

    def init(self, protocol_handler: QicProtocolHandler) -> None:
        self.protocol_handler = protocol_handler

    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        pass


    ######################################################
    # implements InboundHandler
    ######################################################

    ######################################################
    # Implements InboundHandler
    ######################################################

    def send_res_headers(self, tur):
        raise Sink()

    def send_res_content(self, tur, data, ofs, len, callback):
        raise Sink()

    def send_end_tour(self, tur, keep_alive, callback):
        raise Sink()

    def on_protocol_error(self, e: ProtocolException, stk: List[str]) -> bool:
        pass

