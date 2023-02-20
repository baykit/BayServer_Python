import os

from baykit.bayserver import bayserver as bs
from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.http_exception import HttpException
from baykit.bayserver.protocol.protocol_exception import ProtocolException
from baykit.bayserver.sink import Sink as Sink

from baykit.bayserver.tour.send_file_yacht import SendFileYacht
from baykit.bayserver.taxi.taxi_runner import TaxiRunner
from baykit.bayserver.agent.transporter.plain_transporter import PlainTransporter
from baykit.bayserver.agent.transporter.spin_read_transporter import SpinReadTransporter

from baykit.bayserver.tour import tour
from baykit.bayserver.tour.content_consume_listener import ContentConsumeListener
from baykit.bayserver.tour.send_file_train import SendFileTrain
from baykit.bayserver.tour.read_file_taxi import ReadFileTaxi
from baykit.bayserver.docker.harbor import Harbor

from baykit.bayserver.util.headers import Headers
from baykit.bayserver.util.http_status import HttpStatus
from baykit.bayserver.util.mimes import Mimes
from baykit.bayserver.util.gzip_compressor import GzipCompressor
from baykit.bayserver.util.io_util import IOUtil

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

        self.tour.ship.send_headers(self.tour.ship_id, self.tour)
        self.header_sent = True

    def send_redirect(self, chk_tour_id, status, location):
        self.tour.check_tour_id(chk_tour_id)

        if self.header_sent:
            BayLog.error("Try to redirect after response header is sent (Ignore)")
        else:
            self.set_consume_listener(ContentConsumeListener.dev_null)
            self.tour.ship.send_redirect(self.tour.ship_id, self.tour, status, location)
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
            consumed_cb()
            return

        if not self.header_sent:
            raise Sink("Header not sent")

        BayLog.debug("%s sendContent len=%d", self.tour, length)

        if self.tour.is_zombie():
            return True

        if self.consume_listener is None:
            raise Sink("Response consume listener is null")

        self.bytes_posted += length

        BayLog.debug("%s posted res content len=%d posted=%d limit=%d consumed=%d",
                    self.tour, length, self.bytes_posted, self.bytes_limit, self.bytes_consumed)
        if 0 < self.bytes_limit < self.bytes_posted:
            raise ProtocolException("Post data exceed content-length: " + self.bytes_posted + "/" + self.bytes_limit)

        if self.can_compress:
            self.get_compressor().compress(buf, ofs, length, consumed_cb)
        else:
            try:
                self.tour.ship.send_res_content(self.tour.ship_id, self.tour, buf, ofs, length, consumed_cb)
            except IOError as e:
                consumed_cb()
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

        if not self.tour.is_zombie() and self.tour.city is not None:
            self.tour.city.log(self.tour)

        # send end message
        if self.can_compress:
            self.get_compressor().finish()

        # Callback
        def callback():
            self.tour.ship.return_tour(self.tour)

        try:
            self.tour.ship.send_end_tour(self.tour.ship_id, chk_id, self.tour, callback)
        except IOError as e:
            callback()
            raise e

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

        if not self.tour.is_zombie():
            ContentConsumeListener.call(self.consume_listener, length, resume)


    def send_http_exception(self, chk_tour_id, http_ex):
        if http_ex.status == HttpStatus.MOVED_TEMPORARILY or http_ex.status == HttpStatus.MOVED_PERMANENTLY:
            self.send_redirect(chk_tour_id, http_ex.status, http_ex.location)
        else:
            self.send_error(chk_tour_id, http_ex.status, http_ex.message(), http_ex)



    def send_error(self, chk_tour_id, status=HttpStatus.INTERNAL_SERVER_ERROR, msg="", err=None):
        self.tour.check_tour_id(chk_tour_id)

        if self.tour.is_zombie():
            return

        if isinstance(err, HttpException):
            status = err.status
            msg = err.message


        if self.header_sent:
            BayLog.warn("Try to send error after response header is sent (Ignore)");
            BayLog.warn("%s: status=%d, message=%s", self, status, msg);
            if err:
                BayLog.error_e(err);
        else:
            self.set_consume_listener(ContentConsumeListener.dev_null)
            self.tour.ship.send_error(self.tour.ship_id, self.tour, status, msg, err)
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
                    txi = ReadFileTaxi(bufsize);
                    self.yacht.init(self.tour, file, txi);
                    txi.init(infile, self.yacht)
                    if not TaxiRunner.post(txi):
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
            self.compressor = GzipCompressor(lambda new_buf, new_ofs, new_len, callback:
                self.tour.ship.send_res_content(self.tour.ship_id, self.tour, new_buf, new_ofs, new_len, callback))

        return self.compressor


    def buffer_available(self):
          return self.bytes_posted - self.bytes_consumed < self.buffer_size


