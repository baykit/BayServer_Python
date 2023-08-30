from bayserver_core.sink import Sink

from bayserver_core.agent.transporter.data_listener import DataListener
from bayserver_core.util.reusable import Reusable
from bayserver_core.util.counter import Counter

#
# Yacht wraps input stream
#
class Yacht(DataListener, Reusable):

    # class variables
    oid_counter = Counter()
    yacht_id_counter = Counter()

    YACHT_ID_NOCHECK = -1
    INVALID_YACHT_ID = 0

    def __init__(self):
        self.object_id = Yacht.oid_counter.next()
        self.yacht_id = Yacht.INVALID_YACHT_ID

    def init_yacht(self):
        self.yacht_id = Yacht.yacht_id_counter.next()


    ######################################################
    # Implements DataListener
    ######################################################
    def notify_connect(self):
        raise Sink()

    def notify_handshake_done(self, proto):
        raise Sink()

    def notify_protocol_error(self, e):
        raise Sink()
