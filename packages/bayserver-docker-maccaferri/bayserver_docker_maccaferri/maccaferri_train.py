import io
import tempfile
import threading
import time
import traceback
from typing import Dict, Optional

from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.http_exception import HttpException
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.tour.tour import Tour
from bayserver_core.train.train import Train
from bayserver_core.train.train_runner import TrainRunner
from bayserver_core.util.class_util import ClassUtil
from bayserver_core.tour.content_consume_listener import ContentConsumeListener
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_docker_maccaferri import maccaferri_docker as md


class MaccaferriTrain(Train, ReqContentHandler):

    READ_CHUNK_SIZE = 8192
    docker: "md.MaccaferriDocker"
    tour: Tour
    tour_id: int
    app: str
    env: Dict[str, str]
    available: bool
    lock: threading.RLock
    tmpfile: Optional[str]
    req_cont: Optional[bytearray]


    def __init__(self, dkr: "md.MaccaferriDocker", tur: Tour, app: str, env: Dict[str, str]):
        super().__init__()
        self.docker = dkr
        self.tour = tur
        self.tour_id = tur.tour_id
        self.app = app
        self.env = env
        self.available = False
        self.lock = threading.RLock()
        self.tmpfile = None
        self.req_cont = None



    def __str__(self):
        return ClassUtil.get_local_name(self.__class__)

    def start_tour(self):
        self.tour.req.set_content_handler(self)
        self.req_cont = None
        self.tmpfile = None

        if self.env.get("CONTENT_LENGTH"):
            req_cont_len = int(self.env["CONTENT_LENGTH"])
        else:
            req_cont_len = 0

        if req_cont_len <= self.docker.post_cache_threshold:
            # Cache content in memory
            self.req_cont = bytearray(0)
        else:
            # Content save on disk
            self.tmpfile = tempfile.TemporaryFile(mode="w+b", prefix="macaferri_upload")




    def depart(self):

        try:

            if StringUtil.eq_ignorecase(self.tour.req.method, "post"):
                BayLog.debug("%s Maccaferri: posted: content-length: %s", self.tour, self.env["CONTENT_LENGTH"])

            if BayServer.harbor.trace_header():
                for key in self.env.keys():
                    value = self.env[key]
                    BayLog.info("%s Maccaferri: env:%s=%s", self.tour, key, value)

            def start_response(status_str, header_list):
                pos = status_str.find(" ")
                if pos >= 0:
                    code = int(status_str[0:pos])
                else:
                    code = int(status_str)

                self.tour.res.headers.status = code
                for item in header_list:
                    self.tour.res.headers.add(item[0], item[1])

            body = self.docker.app_callable(self.env, start_response)


            def callback(length, resume):
                if resume:
                    self.available = True

            self.tour.res.set_res_consume_listener(callback)
            self.tour.res.send_res_headers(self.tour_id)

            # Send contents
            for fragment in body:
                BayLog.trace("%s Maccaferri: body fragment: len=%d", self.tour, len(fragment))
                self.available = self.tour.res.send_res_content(self.tour_id, fragment, 0, len(fragment))
                while not self.available:
                    time.sleep(0.1)


            self.tour.res.end_res_content(self.tour_id)

        except HttpException as e:
            raise e

        except BaseException as e:
            BayLog.error("%s Maccaferri: Catch error: %s", self.tour, e)
            BayLog.error_e(e, traceback.format_stack())
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, "Maccaferri error")

        finally:
            BayLog.trace("%s Maccaferri: process ended", self.tour)


    def on_read_req_content(self, tur: "Tour", buf: bytearray, start: int, length: int, lis: ContentConsumeListener):
        BayLog.info("%s Maccaferri:onReadReqContent: start=%d len=%d", tur, start, length)

        if self.req_cont is not None:
            # Cache content in memory
            self.req_cont.extend(buf[start:start+length])

        elif self.tmpfile is not None:
            # Content save on disk
            self.tmpfile.write(buf[start:start+length])

        tur.req.consumed(Tour.TOUR_ID_NOCHECK, length, lis)
        return True


    def on_end_req_content(self, tur: "Tour"):
        BayLog.trace("%s Maccaferri:endReqContent", tur)

        wsgi_input = None
        if self.req_cont is not None:
            # Cache content in memory
            wsgi_input = io.BytesIO(self.req_cont)

        elif self.tmpfile is not None:
            # Content save on disk
            self.tmpfile.seek(0)
            wsgi_input = self.tmpfile

        self.env["wsgi.input"] = wsgi_input

        if not TrainRunner.post(self):
            raise HttpException.new(HttpStatus.SERVICE_UNAVAILABLE, "TrainRunner is busy")


    def on_abort_req(self, tur):
        BayLog.trace("%s Maccaferri:abort", tur)

        if self.tmpfile is not None:
            self.tmpfile.close()
            self.tmpfile = None

        return False


    def on_timer(self) -> None:
        pass
