from bayserver_core import bayserver as bs

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.http_exception import HttpException
from bayserver_core.symbol import Symbol
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.sink import Sink
from bayserver_core.tour import tour
from bayserver_core.tour.content_consume_listener import ContentConsumeListener
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.reusable import Reusable
from bayserver_core.util.data_consume_listener import DataConsumeListener


class TourReq(Reusable):

    tour: "Tour"
    key: int
    url: str
    protocol: str
    method: str

    headers: Headers

    rewritten_uri: str
    query_string: str
    path_info: str
    script_name: str
    req_host: str
    req_port: int

    remote_user: str
    remote_pass: str

    remote_address: str
    remote_port: int
    remote_host_func: DataConsumeListener

    server_address: str
    server_port: int
    server_name: str
    charset: str

    bytes_posted: int
    bytes_consumed: int
    bytes_limit: int
    content_handler: ReqContentHandler
    available: bool
    ended: bool

    def __init__(self, tur):
        self.tour = tur
        self.key = None
        self.uri = None
        self.protocol = None
        self.method = None
        self.headers = Headers()
        self.rewritten_uri = None
        self.query_string = None
        self.path_info = None
        self.script_name = None
        self.req_host = None
        self.req_port = None

        self.remote_user = None
        self.remote_pass = None

        self.remote_address = None
        self.remote_port = None
        self.remote_host_func = None    # function. (Remote host is resolved on demand since performance reason)
        self.server_address = None
        self.server_port = None
        self.server_name = None

        self.charset = None
        self.content_handler = None

        self.bytes_posted = None
        self.bytes_consumed = None
        self.bytes_limit = None

        self.consume_listener = None
        self.available = None
        self.ended = None

    def init(self, key):
        self.key = key

    ######################################################
    # Implements Reusable
    ######################################################
    def reset(self):
        self.headers.clear()

        self.uri = None
        self.method = None
        self.protocol = None
        self.bytes_posted = 0
        self.bytes_consumed = 0
        self.bytes_limit = 0

        self.key = 0

        self.rewritten_uri = None
        self.query_string = None
        self.path_info = None
        self.script_name = None
        self.req_host = None
        self.req_port = 0

        self.remote_user = None
        self.remote_pass = None

        self.remote_address = None
        self.remote_port = 0
        self.remote_host_func = None
        self.server_address = None
        self.server_port = 0
        self.server_name = None
        self.charset = None

        self.content_handler = None
        self.consume_listener = None
        self.available = False
        self.ended = False

    ######################################################
    # other methods
    ######################################################
    def remote_host(self):
        return self.remote_host_func()

    def set_limit(self, limit: int):
        if limit < 0:
            raise Sink("invalid limit")

        self.bytes_limit = limit
        self.bytes_posted = 0
        self.bytes_consumed = 0
        self.available = True

    def post_req_content(self, check_id: int, data: bytearray, start: int, length: int, lis: ContentConsumeListener):
        self.tour.check_tour_id(check_id)

        data_passed = False

        # If has error, only read content. (Do not call content handler)
        if self.tour.error is not None:
            BayLog.debug("%s tour has error.", self.tour)

        elif not self.tour.is_reading():
            raise HttpException(HttpStatus.BAD_REQUEST, "%s tour is not reading (state=%d).", self.tour, self.tour.state)

        elif self.content_handler is None:
            BayLog.warn("%s content read, but no content handler", self.tour)

        elif self.bytes_posted + length > self.bytes_limit:
            raise HttpException(
                HttpStatus.BAD_REQUEST,
                BayMessage.get(
                    Symbol.HTP_READ_DATA_EXCEEDED,
                    self.bytes_posted + length,
                    self.bytes_limit))

        else:
            self.content_handler.on_read_req_content(self.tour, data, start, length, lis)
            data_passed = True

        self.bytes_posted += length
        BayLog.debug("%s read content: len=%d posted=%d limit=%d consumed=%d",
                     self.tour, length, self.bytes_posted, self.bytes_limit, self.bytes_consumed)

        if not data_passed:
            return True

        old_available = self.available
        if not self.buffer_available():
            self.available = False

        if old_available and not self.available:
            BayLog.debug("%s request unavailable (_ _): posted=%d consumed=%d", self, self.bytes_posted, self.bytes_consumed);

        return self.available

    def end_content(self, check_id):
        self.tour.check_tour_id(check_id)

        if self.ended:
            raise Sink(f"{self.tour} Request content is already ended")


        if self.bytes_limit >= 0 and self.bytes_posted != self.bytes_limit:
            raise ProtocolException(f"Invalid request data length: {self.bytes_posted}/{self.bytes_limit}")

        if self.content_handler is not None:
            self.content_handler.on_end_req_content(self.tour)

        self.ended = True

    def consumed(self, chk_id: int, length: int, lis: ContentConsumeListener):
        self.tour.check_tour_id(chk_id)

        BayLog.debug("%s content_consumed: len=%d posted=%d", self.tour, length, self.bytes_posted)

        self.bytes_consumed += length
        BayLog.debug("%s reqConsumed: len=%d posted=%d limit=%d consumed=%d",
                        self.tour, length, self.bytes_posted, self.bytes_limit, self.bytes_consumed)

        resume = False
        old_available = self.available
        if self.buffer_available():
            self.available = True

        if not old_available and self.available:
            BayLog.debug("%s request available (^o^): posted=%d consumed=%d", self, self.bytes_posted,
                         self.bytes_consumed);
            resume = True

        lis(length, resume)

    def abort(self):
        BayLog.debug("%s abort tour", self.tour)
        if self.tour.is_preparing():
            self.tour.change_state(self.tour.tour_id, tour.Tour.TourState.ABORTED)
            return True

        elif self.tour.is_reading():
            aborted = True
            if self.content_handler is not None:
                aborted = self.content_handler.on_abort_req(self.tour)
            if aborted:
                self.tour.change_state(self.tour.tour_id, tour.Tour.TourState.ABORTED)
            return aborted

        else:
            BayLog.debug("%s tour is not preparing or not running", self.tour)
            return False

    def set_content_handler(self, hnd):
        BayLog.debug("%s set content handler", self.tour)
        if hnd is None:
            raise Sink("None")

        if self.content_handler is not None:
            raise Sink("content handler already set")

        self.content_handler = hnd


    def buffer_available(self):
          return self.bytes_posted - self.bytes_consumed < bs.BayServer.harbor.tour_buffer_size()

