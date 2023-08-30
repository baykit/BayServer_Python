from bayserver_core.sink import Sink

from bayserver_core.util.counter import Counter
from bayserver_core.agent.transporter.data_listener import DataListener

#
# Boat wraps output stream
#
class Boat(DataListener):

    # class variables
    oid_counter = Counter()
    boat_id_counter = Counter()

    BOAT_ID_NOCHECK = -1
    INVALID_BOAT_ID = 0

    def __init__(self):
        self.object_id = Boat.oid_counter.next()
        self.boat_id = Boat.INVALID_BOAT_ID

    def init_boat(self):
        self.boat_id = Boat.boat_id_counter.next()

    def notify_connect(self):
        raise Sink()

    def notify_read(self, buf, adr):
        raise Sink()

    def notify_eof(self):
        raise Sink()

    def notify_handshake_done(self, proto):
        raise Sink()


    def notify_protocol_error(self, e):
        raise Sink()


    def check_timeout(self, duration_sec):
        raise Sink()


