from abc import ABCMeta, abstractmethod
from typing import ClassVar, Optional, Any, List

from bayserver_core.bay_log import BayLog
from bayserver_core.common.transporter import Transporter
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.util.counter import Counter
from bayserver_core.util.reusable import Reusable


#
# Ship wraps TCP or UDP connection
#
class Ship(Reusable, metaclass=ABCMeta):
    # class variables
    oid_counter: ClassVar[Counter] = Counter()
    ship_id_counter: ClassVar[Counter] = Counter()

    SHIP_ID_NOCHECK = -1
    INVALID_SHIP_ID = 0

    object_id: int
    ship_id: int
    agent_id: int
    rudder: Optional[Rudder]
    transporter: Optional[Transporter]
    initialized: bool
    keeping: bool

    def __init__(self):
        self.object_id = Ship.oid_counter.next()
        self.ship_id = Ship.INVALID_SHIP_ID
        self.agent_id = -1
        self.rudder = None
        self.transporter = None
        self.initialized = False
        self.keeping = False


    def init(self, agt_id: int, rd: Rudder, tp: Transporter):
        if self.initialized:
            raise Sink("ship already initialized")

        self.ship_id = Ship.ship_id_counter.next()
        self.agent_id = agt_id
        self.rudder = rd
        self.transporter = tp
        self.initialized = True
        BayLog.debug("%s initialized", self)

    ######################################################
    # implements Reusable
    ######################################################
    def reset(self):
        BayLog.trace("%s reset", self)

        self.initialized = False
        self.transporter = None
        self.rudder = None
        self.agent_id = -1
        self.ship_id = Ship.INVALID_SHIP_ID
        self.keeping = False

    ######################################################
    # Abstract methods
    ######################################################

    @abstractmethod
    def notify_handshake_done(self, proto: str) -> int:
        pass

    @abstractmethod
    def notify_connect(self) -> int:
        pass

    @abstractmethod
    def notify_read(self, buf: bytes, adr: Any) -> int:
        pass

    @abstractmethod
    def notify_eof(self) -> int:
        pass

    @abstractmethod
    def notify_error(self, e: BaseException, stk: List[str]) -> None:
        pass

    @abstractmethod
    def notify_protocol_error(self, e: ProtocolException, stk: List[str]) -> bool:
        pass

    @abstractmethod
    def notify_close(self) -> None:
        pass

    @abstractmethod
    def check_timeout(self, duration_sec: int) -> bool:
        pass

    ######################################################
    # Other methods
    ######################################################

    def id(self):
        return self.ship_id

    def resume_read(self, check_id):
        self.check_ship_id(check_id)
        self.transporter.req_read(self.rudder)

    def post_close(self):
        self.transporter.req_close(self.rudder)

    def check_ship_id(self, check_id):
        if not self.initialized:
            raise Sink(f"{self} ship not initialized (might be returned ship): {check_id}")

        if check_id != Ship.SHIP_ID_NOCHECK and check_id != self.ship_id:
            raise Sink(f"{self} Invalid ship id (might be returned ship): {check_id}")
