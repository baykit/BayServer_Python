from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.ship.ship import Ship
from bayserver_core.sink import Sink


class ReadOnlyShip(Ship):

    ######################################################
    # Implements Ship
    ######################################################

    def notify_handshake_done(self, proto: str) -> int:
        raise Sink()

    def notify_connect(self) -> int:
        raise Sink()

    def notify_protocol_error(self, e: ProtocolException) -> bool:
        raise Sink()

