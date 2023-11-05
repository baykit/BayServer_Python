import os

from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog
from bayserver_core.http_exception import HttpException
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.sink import Sink as Sink

from bayserver_core.tour.send_file_yacht import SendFileYacht
from bayserver_core.taxi.taxi_runner import TaxiRunner
from bayserver_core.agent.transporter.plain_transporter import PlainTransporter
from bayserver_core.agent.transporter.spin_read_transporter import SpinReadTransporter

from bayserver_core.tour import tour
from bayserver_core.tour.content_consume_listener import ContentConsumeListener
from bayserver_core.tour.send_file_train import SendFileTrain
from bayserver_core.tour.read_file_taxi import ReadFileTaxi
from bayserver_core.docker.harbor import Harbor

from bayserver_core.util.headers import Headers
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.mimes import Mimes
from bayserver_core.util.gzip_compressor import GzipCompressor
from bayserver_core.util.io_util import IOUtil

class TourRes:

    def __init__(self, tur):
        self.tour = tur

        ###########################
        #  Response Header info
        ###########################
        self.headers = Headers()
        self.charset = None
        self.available = None
        self.consume_listener = None

        self.header_sent = None
        self.yacht = None

        ###########################
        #  Response Content info
        ###########################
        self.can_compress = None
        self.compressor = None

        self.bytes_posted = None
        self.bytes_consumed = None
        self.bytes_limit = None
        self.buffer_size = bs.BayServer.harbor.tour_buffer_size
        self.tour_returned = False
        #self.buffer_size = 1024

    def __str__(self):
        return str(self.tour)

    def init(self):
        self.yacht = SendFileYacht()

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        self.charset = None
        self.header_sent = False
        if(self.yacht is not None):
            self.yacht.reset()
        self.yacht = None

        self.available = False
        self.consume_listener = None
        self.can_compress = False
        self.compressor = None
        self.headers.clear()
        self.bytes_posted = 0
        self.bytes_consumed = 0
        self.bytes_limit = 0
        self.tour_returned = False


    ######################################################
    # other methods
    ######################################################

    def send_headers(self, chk_tour_id):
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
        if bs.BayServer.harbor.gzip_comp and \
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
            self.tour.ship.send_headers(self.tour.ship_id, self.tour)
        except IOError as e:
            self.tour.change_state(tour.Tour.TOUR_ID_NOCHECK, tour.Tour.TourState.ABORTED)
            raise e
        finally:
            self.header_sent = True

    def send_redirect(self, chk_tour_id, status, location):
        self.tour.check_tour_id(chk_tour_id)

        if self.header_sent:
            BayLog.error("Try to redirect after response header is sent (Ignore)")
        else:
            self.set_consume_listener(ContentConsumeListener.dev_null)
            try:
                self.tour.ship.send_redirect(self.tour.ship_id, self.tour, status, location)
            except IOError as e:
                self.tour.change_state(tour.Tour.TOUR_ID_NOCHECK, tour.Tour.TourState.ABORTED)
                raise e
            finally:
                self.header_sent = True
                self.end_content(chk_tour_id)

    def set_consume_listener(self, listener):
        self.consume_listener = listener
        self.bytes_consumed = 0
        self.bytes_posted = 0
        self.available = True

    def send_content(self, chk_tour_id, buf, ofs, length):
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

        if self.consume_listener is None:
            raise Sink("Response consume listener is null")

        self.bytes_posted += length
        BayLog.debug("%s posted res content len=%d posted=%d limit=%d consumed=%d",
                    self.tour, length, self.bytes_posted, self.bytes_limit, self.bytes_consumed)

        if 0 < self.bytes_limit < self.bytes_posted:
            raise ProtocolException("Post data exceed content-length: " + self.bytes_posted + "/" + self.bytes_limit)

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
                    self.tour.change_state(tour.Tour.TOUR_ID_NOCHECK, tour.Tour.TourState.ABORTED)
                    raise e

        old_available = self.available
        if not self.buffer_available():
            self.available = False

        if old_available and not self.available:
            BayLog.debug("%s response unavailable (_ _): posted=%d consumed=%d (buffer=%d)",
                         self, self.bytes_posted, self.bytes_consumed, self.buffer_size)

        return self.available

    def end_content(self, chk_id):
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
        def callback():
            self.tour.check_tour_id(chk_id)
            self.tour.ship.return_tour(self.tour)
            self.tour_returned = True

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
            BayLog.debug("%s Tour is returned: %s", self, self.tour_returned)
            if not self.tour_returned:
                self.tour.change_state(tour.Tour.TOUR_ID_NOCHECK, tour.Tour.TourState.ENDED)

    def consumed(self, check_id, length):
        self.tour.check_tour_id(check_id)

        if self.consume_listener is None:
            raise Sink("Response consume listener is null")

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

        if self.tour.is_running():
            ContentConsumeListener.call(self.consume_listener, length, resume)


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
            BayLog.warn("Try to send error after response header is sent (Ignore)");
            BayLog.warn("%s: status=%d, message=%s", self, status, msg);
            if err:
                BayLog.error_e(err);
        else:
            self.set_consume_listener(ContentConsumeListener.dev_null)

            if self.tour.is_zombie() or self.tour.is_aborted():
                # Don't send peer any data
                BayLog.debug("%s Aborted or zombie tour. do nothing: %s state=%s", self, self.tour, self.tour.state)
            else:
                try:
                    self.tour.ship.send_error(self.tour.ship_id, self.tour, status, msg, err)
                except IOError as e:
                    BayLog.error_e(e, "%s Error in sending error", self)
                    self.tour.change_state(tour.Tour.TOUR_ID_NOCHECK, tour.Tour.TourState.ABORTED)
            self.header_sent = True

        self.end_content(chk_tour_id)

    def send_file(self, chk_tour_id, file, charset, async_mode):
        self.tour.check_tour_id(chk_tour_id)

        if self.tour.is_zombie():
            return

        if os.path.isdir(file):
            raise HttpException(HttpStatus.FORBIDDEN, file)
        elif not os.path.exists(file):
            raise HttpException(HttpStatus.NOT_FOUND, file)

        mime_type = None
        rname = os.path.basename(file)

        pos = rname.rfind('.')
        if pos > 0:
            ext = rname[pos + 1:].lower()
            mime_type = Mimes.type(ext)

        if mime_type is None:
            mime_type = "application/octet-stream"

        if mime_type.startswith("text/") and charset is not None:
            mime_type = mime_type + "; charset=" + charset

        file_len = os.path.getsize(file)
        BayLog.debug("%s send_file %s async=%s len=%d", self.tour, file, async_mode, file_len)

        self.headers.set_content_type(mime_type)
        self.headers.set_content_length(file_len)

        try:
            self.send_headers(tour.Tour.TOUR_ID_NOCHECK)

            if async_mode:
                bufsize = self.tour.ship.protocol_handler.max_res_packet_data_size()
                method = bs.BayServer.harbor.file_send_method
                infile = open(file, "rb", buffering=False)

                if method == Harbor.FILE_SEND_METHOD_SELECT:
                    IOUtil.set_non_blocking(infile)
                    tp = PlainTransporter(False, bufsize)
                    self.yacht.init(self.tour, file, tp)
                    tp.init(self.tour.ship.agent.non_blocking_handler, infile, self.yacht)
                    tp.open_valve()

                if method == Harbor.FILE_SEND_METHOD_SPIN:
                    timeout = 10
                    IOUtil.set_non_blocking(infile)
                    tp = SpinReadTransporter(bufsize)
                    self.yacht.init(self.tour, file, tp);
                    tp.init(self.tour.ship.agent.spin_handler, self.yacht, infile, os.path.getsize(file), timeout, None)
                    tp.open_valve()

                elif method == Harbor.FILE_SEND_METHOD_TAXI:
                    txi = ReadFileTaxi(self.tour.ship.agent, bufsize)
                    self.yacht.init(self.tour, file, txi);
                    txi.init(infile, self.yacht)
                    if not TaxiRunner.post(self.tour.ship.agent.agent_id, txi):
                        raise HttpException(HttpStatus.SERVICE_UNAVAILABLE, "Taxi is busy!");

                else:
                    raise Sink();

            else:
                SendFileTrain(self.tour, file).run()
        except HttpException as e:
            raise e
        except Exception as e:
            BayLog.error_e(e)
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, file)

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
          return self.bytes_posted - self.bytes_consumed < self.buffer_size


