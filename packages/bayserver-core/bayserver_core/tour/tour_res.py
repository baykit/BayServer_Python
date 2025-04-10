from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog
from bayserver_core.docker.trouble import Trouble
from bayserver_core.http_exception import HttpException
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.sink import Sink as Sink
from bayserver_core.tour import tour
from bayserver_core.tour.content_consume_listener import ContentConsumeListener, content_consume_listener_dev_null
from bayserver_core.util.gzip_compressor import GzipCompressor
from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus


class TourRes:

    tour: "tour.Tour"

    headers: Headers
    charset: str
    header_send: bool

    available: bool
    bytes_posted: int
    bytes_consumed: int
    bytes_limit: int
    res_consume_listener: ContentConsumeListener
    can_compress: bool
    compressor: GzipCompressor

    def __init__(self, tur):
        self.tour = tur

        ###########################
        #  Response Header info
        ###########################
        self.headers = Headers()
        self.charset = None
        self.available = None
        self.res_consume_listener = None

        self.header_sent = None

        ###########################
        #  Response Content info
        ###########################
        self.can_compress = None
        self.compressor = None

        self.bytes_posted = None
        self.bytes_consumed = None
        self.bytes_limit = None
        self.buffer_size = bs.BayServer.harbor.tour_buffer_size

    def __str__(self):
        return str(self.tour)

    def init(self):
        pass

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        self.charset = None
        self.header_sent = False

        self.available = False
        self.res_consume_listener = None
        self.can_compress = False
        self.compressor = None
        self.headers.clear()
        self.bytes_posted = 0
        self.bytes_consumed = 0
        self.bytes_limit = 0

    ######################################################
    # other methods
    ######################################################

    def send_res_headers(self, chk_tour_id):
        self.tour.check_tour_id(chk_tour_id)
        BayLog.debug("%s send headers", self)

        if self.tour.is_zombie():
            BayLog.debug("%s zombie return", self)
            return

        if self.header_sent:
            BayLog.debug("%s header sent", self)
            return

        self.bytes_limit = self.headers.content_length()

        # Compress check
        if bs.BayServer.harbor.gzip_comp() and \
            self.headers.contains(Headers.CONTENT_TYPE) and \
            self.headers.content_type().lower().startswith("text/") and \
            not self.headers.contains(Headers.CONTENT_ENCODING):

            enc = self.tour.req.headers.get(Headers.ACCEPT_ENCODING)

            if enc is not None:
                for tkn in enc.split(","):
                    if tkn.strip().lower() == "gzip":
                        self.can_compress = True
                        self.headers.set(Headers.CONTENT_ENCODING, "gzip")
                        self.headers.remove(Headers.CONTENT_LENGTH)
                        break

        try:
            handled = False
            if not self.tour.error_handling and self.tour.res.headers.status >= 400:
                trouble = bs.BayServer.harbor.trouble()
                if trouble is not None:
                    cmd = trouble.find(self.tour.res.headers.status)
                    if cmd is not None:
                        err_tour = self.tour.ship.get_error_tour()
                        err_tour.req.uri = cmd.target
                        self.tour.req.headers.copy_to(err_tour.req.headers)
                        self.tour.res.headers.copy_to(err_tour.res.headers)
                        err_tour.req.remote_port = self.tour.req.remote_port
                        err_tour.req.remote_address = self.tour.req.remote_address
                        err_tour.req.server_address = self.tour.req.server_address
                        err_tour.req.server_port = self.tour.req.server_port
                        err_tour.req.server_name = self.tour.req.server_name
                        self.tour.change_state(tour.Tour.TOUR_ID_NOCHECK, tour.Tour.TourState.ZOMBIE)

                        if cmd.method == Trouble.GUIDE:
                            err_tour.go()
                        elif cmd.method == Trouble.TEXT:
                            self.tour.ship.send_headers(self.tour.ship_id, err_tour)
                            data = cmd.target
                            err_tour.res.send_res_content(tour.Tour.TOUR_ID_NOCHECK, err_tour, data, 0, len(data))
                            err_tour.res.send_end_tour(tour.Tour.TOUR_ID_NOCHECK, err_tour)
                        elif cmd.method == Trouble.REROUTE:
                            err_tour.res.send_http_exception(tour.Tour.TOUR_ID_NOCHECK, HttpException.moved_temp(cmd.target))

                        handled = True

            if not handled:
                self.tour.ship.send_headers(self.tour.ship_id, self.tour)

        except IOError as e:
            self.tour.change_state(chk_tour_id, tour.Tour.TourState.ABORTED)
            raise e
        finally:
            self.header_sent = True

    def send_redirect(self, chk_tour_id, status, location):
        self.tour.check_tour_id(chk_tour_id)

        if self.header_sent:
            BayLog.error("Try to redirect after response header is sent (Ignore)")
        else:
            self.set_res_consume_listener(ContentConsumeListener.dev_null)
            try:
                self.tour.ship.send_redirect(self.tour.ship_id, self.tour, status, location)
            except IOError as e:
                self.tour.change_state(chk_tour_id, tour.Tour.TourState.ABORTED)
                raise e
            finally:
                self.header_sent = True
                self.end_res_content(chk_tour_id)

    def set_res_consume_listener(self, listener):
        self.res_consume_listener = listener
        self.bytes_consumed = 0
        self.bytes_posted = 0
        self.available = True

    def send_res_content(self, chk_tour_id, buf, ofs, length):
        self.tour.check_tour_id(chk_tour_id)
        BayLog.debug("%s send content: len=%d", self, length)

        # Callback
        def consumed_cb():
            self.consumed(chk_tour_id, length)

        if self.tour.is_zombie():
            BayLog.debug("%s zombie return", self)
            self.bytes_posted += length
            consumed_cb()
            return True

        if not self.header_sent:
            raise Sink("Header not sent")

        self.bytes_posted += length
        BayLog.debug("%s posted res content len=%d posted=%d limit=%d consumed=%d",
                    self.tour, length, self.bytes_posted, self.bytes_limit, self.bytes_consumed)

        if 0 < self.bytes_limit < self.bytes_posted:
            raise ProtocolException("Post data exceed content-length: %d/%d", self.bytes_posted, self.bytes_limit)

        if self.tour.is_zombie() or self.tour.is_aborted():
            # Don't send peer any data
            BayLog.debug("%s Aborted or zombie tour. do nothing: %s state=%s", self, self.tour, self.tour.state)
            consumed_cb()
        else:
            if self.can_compress:
                self.get_compressor().compress(buf, ofs, length, consumed_cb)
            else:
                try:
                    self.tour.ship.send_res_content(self.tour.ship_id, self.tour, buf, ofs, length, consumed_cb)
                except IOError as e:
                    consumed_cb()
                    self.tour.change_state(chk_tour_id, tour.Tour.TourState.ABORTED)
                    raise e

        old_available = self.available
        if not self.buffer_available():
            self.available = False

        if old_available and not self.available:
            BayLog.debug("%s response unavailable (_ _): posted=%d consumed=%d (buffer=%d)",
                         self, self.bytes_posted, self.bytes_consumed, self.buffer_size)

        return self.available

    def end_res_content(self, chk_id):
        self.tour.check_tour_id(chk_id)

        BayLog.debug("%s end ResContent: chk_id=%d", self, chk_id)
        if self.tour.is_ended():
            BayLog.debug("%s Tour is already ended (Ignore).", self)
            return

        if not self.tour.is_zombie() and self.tour.city is not None:
            self.tour.city.log(self.tour)

        # send end message
        if self.can_compress:
            self.get_compressor().finish()

        # Callback
        tour_returned = []
        callback = lambda: (
            #BayLog.debug("%s called back to return tour", self),
            self.tour.check_tour_id(chk_id),
            self.tour.ship.return_tour(self.tour),
            tour_returned.append(True))

        try:
            if self.tour.is_zombie() or self.tour.is_aborted():
                # Don't send peer any data. Do nothing
                BayLog.debug("%s Aborted or zombie tour. do nothing: %s state=%s", self, self.tour, self.tour.state)
                callback()
            else:
                try:
                    self.tour.ship.send_end_tour(self.tour.ship_id, self.tour, callback)
                except IOError as e:
                    BayLog.debug("%s Error on sending end tour", self)
                    callback()
                    raise e
        finally:
            # If tour is returned, we cannot change its state because
            # it will become uninitialized.
            BayLog.debug("%s Tour is returned: %s", self, tour_returned)
            if len(tour_returned) == 0:
                self.tour.change_state(chk_id, tour.Tour.TourState.ENDED)

    def consumed(self, check_id, length):
        self.tour.check_tour_id(check_id)

        self.bytes_consumed += length

        BayLog.debug("%s resConsumed: len=%d posted=%d consumed=%d limit=%d",
                    self.tour, length, self.bytes_posted, self.bytes_consumed, self.bytes_limit)

        resume = False
        old_available = self.available
        if self.buffer_available():
            self.available = True

        if not old_available and self.available:
            BayLog.debug("%s response available (^o^): posted=%d consumed=%d", self, self.bytes_posted,
                         self.bytes_consumed);
            resume = True

        if not self.tour.is_zombie():
            if self.res_consume_listener is None:
                BayLog.debug("Consume listener is null, so can not invoke callback")
            else:
                self.res_consume_listener(length, resume)


    def send_http_exception(self, chk_tour_id, http_ex):
        if http_ex.status == HttpStatus.MOVED_TEMPORARILY or http_ex.status == HttpStatus.MOVED_PERMANENTLY:
            self.send_redirect(chk_tour_id, http_ex.status, http_ex.location)
        else:
            self.send_error(chk_tour_id, http_ex.status, http_ex.args, http_ex)



    def send_error(self, chk_tour_id, status=HttpStatus.INTERNAL_SERVER_ERROR, msg="", err=None):
        self.tour.check_tour_id(chk_tour_id)

        if self.tour.is_zombie():
            return

        if isinstance(err, HttpException):
            status = err.status
            msg = err.args

        if self.header_sent:
            BayLog.debug("Try to send error after response header is sent (Ignore)");
            BayLog.debug("%s: status=%d, message=%s", self, status, msg);
            if err:
                BayLog.error_e(err);
        else:
            self.set_res_consume_listener(content_consume_listener_dev_null)

            if self.tour.is_zombie() or self.tour.is_aborted():
                # Don't send peer any data
                BayLog.debug("%s Aborted or zombie tour. do nothing: %s state=%s", self, self.tour, self.tour.state)
            else:
                try:
                    self.tour.ship.send_error(self.tour.ship_id, self.tour, status, msg, err)
                except IOError as e:
                    BayLog.debug_e(e, "%s Error in sending error", self)
                    self.tour.change_state(chk_tour_id, tour.Tour.TourState.ABORTED)
            self.header_sent = True

        self.end_res_content(chk_tour_id)

    def get_compressor(self):
        if self.compressor is None:
            sip_id = self.tour.ship.ship_id
            tur_id = self.tour.tour_id
            def gz_callback(new_buf, new_ofs, new_len, callback):
                try:
                    self.tour.ship.send_res_content(sip_id, self.tour, new_buf, new_ofs, new_len, callback)
                except IOError as e:
                    self.tour.change_state(tur_id, tour.Tour.TourState.ABORTED)
                    raise e

            self.compressor = GzipCompressor(gz_callback)

        return self.compressor


    def buffer_available(self):
          return self.bytes_posted - self.bytes_consumed < bs.BayServer.harbor.tour_buffer_size()


