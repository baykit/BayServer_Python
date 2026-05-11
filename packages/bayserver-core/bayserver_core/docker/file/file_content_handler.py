import traceback

from bayserver_core.bay_log import BayLog
from bayserver_core.http_exception import HttpException
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.tour.tour import Tour
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.directory_exception import DirectoryException
from bayserver_core.util.http_status import HttpStatus


class FileContentHandler(ReqContentHandler):

    def __init__(self, tur: Tour, path: str, charset: str, list_files: bool):
        self.tour = tur
        self.path = path
        self.charset = charset
        self.list_files = list_files
        self.abortable = True

    ######################################################
    # Implements ReqContentHandler
    ######################################################

    def on_read_req_content(self, tur: Tour, buf: bytes, start: int, length: int, lis: DataConsumeListener):
        BayLog.debug("%s file:onReadContent(Ignore) len=%d", tur, length)
        tur.req.consumed(tur.tour_id, length, lis)

    def on_end_req_content(self, tur: Tour):
        BayLog.debug("%s file:endContent", tur)
        self._req_start_tour()
        self.abortable = False

    def on_abort_req(self, tur: Tour):
        BayLog.debug("%s file:onAbort aborted=%s", tur, self.abortable)
        return self.abortable

    ######################################################
    # Sending file methods
    ######################################################

    def _req_start_tour(self):
        BayLog.debug("%s reqStartTour", self.tour)
        try:
            self.tour.res.send_file(self.path, self.charset)
        except DirectoryException:
            self._handle_directory()
        except FileNotFoundError:
            raise HttpException(HttpStatus.NOT_FOUND, self.path)
        except HttpException:
            raise
        except Exception as e:
            BayLog.error_e(e, traceback.format_stack())
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, self.path)

    def _handle_directory(self):
        if self.list_files:
            from bayserver_core.docker.file.directory_train import DirectoryTrain
            train = DirectoryTrain(self.tour, self.path)
            train.start_tour()
        else:
            raise HttpException(HttpStatus.FORBIDDEN, "Directory scan is prohibited")
