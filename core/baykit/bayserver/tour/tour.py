import threading

from baykit.bayserver import bayserver as bs
from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.http_exception import HttpException
from baykit.bayserver.watercraft.ship import Ship
from baykit.bayserver.sink import Sink
from baykit.bayserver.tour import tour_req
from baykit.bayserver.tour import tour_res
from baykit.bayserver.util.counter import Counter
from baykit.bayserver.util.http_status import HttpStatus
from baykit.bayserver.util.reusable import Reusable
from baykit.bayserver.util.exception_util import ExceptionUtil


class Tour(Reusable):

    class TourState:
        UNINITIALIZED = 0
        PREPARING = 1
        RUNNING = 2
        ABORTED = 3
        ENDED = 4
        ZOMBIE = 5

    # class variables
    oid_counter = Counter()
    tour_id_counter = Counter()

    TOUR_ID_NOCHECK = -1
    INVALID_TOUR_ID = 0

    def __init__(self):
        self.ship = None
        self.ship_id = None
        self.obj_id = Tour.oid_counter.next() # object id
        self.req = tour_req.TourReq(self)
        self.res = tour_res.TourRes(self)
        self.lock = threading.RLock()
        self.tour_id = Tour.INVALID_TOUR_ID
        self.error_handling = None
        self.town = None
        self.city = None
        self.club = None
        self.interval = None
        self.is_secure = None
        self.error = None
        self.state = None

        self.reset()


    def id(self):
        return self.tour_id

    def __str__(self):
        return f"{self.ship} tour#{self.tour_id}/{self.obj_id} [key={self.req.key}]";

    ######################################################
    # implements Reusable
    ######################################################
    def reset(self):
        self.city = None
        self.town = None
        self.club = None
        self.error_handling = False
        self.tour_id = Tour.INVALID_TOUR_ID
        self.interval = 0
        self.is_secure = False
        self.change_state(Tour.TOUR_ID_NOCHECK, Tour.TourState.UNINITIALIZED)
        self.error = None
        self.req.reset()
        self.res.reset()



    ######################################################
    # other methods
    ######################################################
    def init(self, key, sip):
        if self.is_initialized():
            raise Sink(f"{self} Tour already initialized")

        self.ship = sip
        self.ship_id = sip.ship_id
        if self.ship_id == Ship.INVALID_SHIP_ID:
            raise Sink()

        self.tour_id = Tour.tour_id_counter.next()
        self.change_state(Tour.TOUR_ID_NOCHECK, Tour.TourState.PREPARING)

        self.req.init(key)
        self.res.init()

        BayLog.debug("%s initialized", self)

    def go(self):
        self.change_state(Tour.TOUR_ID_NOCHECK, Tour.TourState.RUNNING)

        city = self.ship.port_docker.find_city(self.req.req_host)
        if city is None:
            city = bs.BayServer.find_city(self.req.req_host)
        BayLog.debug("%s GO TOUR! ...( ^_^)/: url=%s", self, self.req.uri);

        if city is None:
            raise HttpException(HttpStatus.NOT_FOUND, self.req.uri)
        else:
            try:
                city.enter(self)
            except Sink as e:
                raise e
            except HttpException as e:
                BayLog.error_e(e)
                raise e
            except BaseException as e:
                BayLog.error_e(e)
                raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, ExceptionUtil.message(e))

    def is_valid(self):
        return self.state == Tour.TourState.PREPARING or self.state == Tour.TourState.RUNNING

    def is_running(self):
        return self.state == Tour.TourState.RUNNING

    def is_zombie(self):
        return self.state == Tour.TourState.ZOMBIE

    def is_aborted(self):
        return self.state == Tour.TourState.ABORTED

    def is_initialized(self):
        return self.state != Tour.TourState.UNINITIALIZED

    def change_state(self, chk_id, new_state):
        BayLog.trace("%s change state: %s", self, new_state)
        self.check_tour_id(chk_id)
        self.state = new_state

    def check_tour_id(self, chk_id):
        if chk_id == Tour.TOUR_ID_NOCHECK:
            return

        if not self.is_initialized():
            raise Sink("%s Tour not initialized", self)

        if chk_id != self.tour_id:
            raise Sink("%s Invalid tours id: %s", self, "" if chk_id is None else str(chk_id))

