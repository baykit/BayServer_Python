from bayserver_core import bayserver as bs

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.sink import Sink
from bayserver_core.tour import tour
from bayserver_core.tour.content_consume_listener import ContentConsumeListener
from bayserver_core.util.headers import Headers
from bayserver_core.util.reusable import Reusable


class TourReq(Reusable):

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

    def set_consume_listener(self, limit, listener):
        if limit < 0:
            raise Sink("invalid limit")

        self.bytes_limit = limit
        self.consume_listener = listener
        self.bytes_posted = 0
        self.bytes_consumed = 0
        self.available = True

    def post_content(self, check_id, data, start, length):
        self.tour.check_tour_id(check_id)

        data_passed = False
        if not self.tour.is_running():
            BayLog.debug("%s tour is not running.", self.tour);

        elif self.content_handler is None:
            BayLog.warn("%s content read, but no content handler", self.tour)

        elif self.consume_listener is None:
            raise Sink("Request consume listener is null")

        elif self.bytes_posted + length > self.bytes_limit:
            raise ProtocolException(
                BayMessage.get(
                    Symbol.HTP_READ_DATA_EXCEEDED,
                    self.bytes_posted + length,
                    self.bytes_limit))

        # If has error, only read content. (Do not call content handler)
        elif self.tour.error is not None:
            BayLog.debug("%s tour has error.", self.tour)

        else:
            self.content_handler.on_read_content(self.tour, data, start, length)
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
            self.content_handler.on_end_content(self.tour)

        self.ended = True

    def consumed(self, chk_id, length):
        self.tour.check_tour_id(chk_id)

        BayLog.debug("%s content_consumed: len=%d posted=%d", self.tour, length, self.bytes_posted)

        if self.consume_listener is None:
            raise Sink("Request consume listener is null")

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

        ContentConsumeListener.call(self.consume_listener, length, resume)


    def abort(self):
        if not self.tour.is_preparing():
            BayLog.debug("%s cannot abort non-preparing tour", self.tour)
            return False

        BayLog.debug("%s req abort", self.tour)
        if self.tour.is_aborted():
            raise Sink("tour is already aborted")

        aborted = True
        if self.tour.is_running() and self.content_handler is not None:
            aborted = self.content_handler.on_abort(self.tour)

        if aborted:
            self.tour.change_state(tour.Tour.TOUR_ID_NOCHECK, tour.Tour.TourState.ABORTED)

        return aborted

    def set_content_handler(self, hnd):
        BayLog.debug("%s set content handler", self.tour)
        if hnd is None:
            raise Sink("None")

        if self.content_handler is not None:
            raise Sink("content handler already set")

        self.content_handler = hnd


    def buffer_available(self):
          return self.bytes_posted - self.bytes_consumed < bs.BayServer.harbor.tour_buffer_size

