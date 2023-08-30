import socket

from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.util.counter import Counter
from bayserver_core.util.reusable import Reusable

#
# Ship wraps TCP or UDP connection
#
class Ship(Reusable):
    # class variables
    oid_counter = Counter()
    ship_id_counter = Counter()

    SHIP_ID_NOCHECK = -1
    INVALID_SHIP_ID = 0

    def __init__(self):
        self.object_id = Ship.oid_counter.next()
        self.ship_id = Ship.INVALID_SHIP_ID
        self.agent = None
        self.postman = None
        self.socket = None
        self.initialized = None
        self.protocol_handler = None
        self.keeping = None

    ######################################################
    # implements Reusable
    ######################################################
    def reset(self):
        BayLog.trace("%s reset", self)

        self.initialized = False
        self.postman.reset()
        self.postman = None  # for reloading certification
        self.agent = None
        self.ship_id = Ship.INVALID_SHIP_ID
        self.socket = None
        self.protocol_handler = None
        self.keeping = False

    ######################################################
    # Other methods
    ######################################################

    def init(self, skt, agt, postman):
        if self.initialized:
            raise Sink("ship already initialized")

        self.ship_id = Ship.ship_id_counter.next()
        self.agent = agt
        self.postman = postman
        self.socket = skt
        self.initialized = True
        BayLog.debug("%s initialized", self)

    def set_protocol_handler(self, proto_hnd):
        self.protocol_handler = proto_hnd
        proto_hnd.ship = self
        BayLog.trace("%s protocol handler is set", self)

    def id(self):
        return self.ship_id

    def protocol(self):
        return "unknown" if self.protocol_handler is None else self.protocol_handler.protocol()

    def resume(self, check_id):
        self.check_ship_id(check_id);
        self.postman.open_valve()

    def check_ship_id(self, check_id):
        if not self.initialized:
            raise Sink(f"{self} ships not initialized (might be returned ships): {check_id}")

        if check_id != Ship.SHIP_ID_NOCHECK and check_id != self.ship_id:
            raise Sink(f"{self} Invalid ships id (might be returned ships): {check_id}")
