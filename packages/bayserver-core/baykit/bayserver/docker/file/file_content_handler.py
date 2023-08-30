from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.tour.tour import Tour
from baykit.bayserver.tour.req_content_handler import ReqContentHandler

class FileContentHandler(ReqContentHandler):

    def __init__(self, path):
        self.path = path
        self.abortable = True

    def on_read_content(self, tur, buf, start, length):
        BayLog.debug("%s onReadReqContent(Ignore) len=%d", tur, length)

    def on_end_content(self, tur):
        BayLog.debug("%s endReqContent", tur)
        tur.res.send_file(Tour.TOUR_ID_NOCHECK, self.path, tur.res.charset, True)
        self.abortable = False

    def on_abort(self, tur):
        BayLog.debug("%s onAbortReq aborted=%s", tur, self.abortable)
        return self.abortable
