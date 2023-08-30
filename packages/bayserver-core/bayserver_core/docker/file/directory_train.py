import io
import os
import time

from bayserver_core.bay_log import BayLog
from bayserver_core.http_exception import HttpException

from bayserver_core.train.train import Train
from bayserver_core.train.train_runner import TrainRunner
from bayserver_core.tour.req_content_handler import ReqContentHandler

from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.http_status import HttpStatus

class DirectoryTrain(Train, ReqContentHandler):

    def __init__(self, tur, path):
        super().__init__(tur)
        self.path = path
        self.available = False
        self.abortable = True

    def start_tour(self):
        self.tour.req.set_content_handler(self)

    #######################################################
    # Implements Train
    #######################################################

    def depart(self):
        try:

            self.tour.res.headers.set_content_type("text/html")


            def callback(len, resume):
                if resume:
                    self.available = True

            self.tour.res.set_consume_listener(callback)

            self.tour.res.send_headers(self.tour_id)

            w = io.StringIO()
            w.write("<html><body><br>")

            if self.tour.req.uri != "/":
                self.print_link(w, "../")

            for f in os.listdir(self.path):
                if os.path.isdir(os.path.join(self.path, f)):
                    if f != "." and f != "..":
                        self.print_link(w, f"{f}/")
                else:
                    self.print_link(w, f)

            w.write("</body></html>")
            bytes = StringUtil.to_bytes(w.getvalue())
            w.close()

            BayLog.trace("%s Directory: send contents: len=%d", self.tour, len(bytes))

            self.available = self.tour.res.send_content(self.tour_id, bytes, 0, len(bytes))

            while not self.available:
                time.sleep(0.1)

            self.tour.res.end_content(self.tour_id)

        except IOError as e:
            BayLog.error_e(e)
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, e)

    #######################################################
    # Implements ReqContentHandler
    #######################################################

    def on_read_content(self, tur, buf, start, length):
        BayLog.debug("%s onReadContent(Ignore) len=%d", tur, length)

    def on_end_content(self, tur):
        BayLog.debug("%s endContent", tur)

        self.abortable = False

        if not TrainRunner.post(self):
            raise HttpException(HttpStatus.SERVICE_UNAVAILABLE, "TourRunner is busy")

    def on_abort(self, tur):
        BayLog.debug("%s onAbort aborted=%s", tur, self.abortable)
        return self.abortable

    def print_link(self, w, path):
        w.write(f"<a href='{path}'>")
        w.write(path)
        w.write("</a><br>")


