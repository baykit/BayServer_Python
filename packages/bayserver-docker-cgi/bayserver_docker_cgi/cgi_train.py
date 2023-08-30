import threading
import time
import os
from subprocess import Popen

from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.http_exception import HttpException
from bayserver_core.tour.req_content_handler import ReqContentHandler

from bayserver_core.train.train import Train
from bayserver_core.train.train_runner import TrainRunner
from bayserver_core.tour.tour import Tour

from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.http_util import HttpUtil
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.class_util import ClassUtil


class CgiTrain(Train, ReqContentHandler):
    READ_CHUNK_SIZE = 8192

    def __init__(self, dkr, tur):
        super().__init__(tur)
        self.cgi_docker = dkr
        self.env = None
        self.available = None
        self.lock = None
        self.process = None
        self.std_in = None
        self.std_out = None
        self.std_err = None

    def __str__(self):
        return ClassUtil.get_local_name(self.__class__)

    def start_tour(self, env):
        self.env = env
        self.available = False
        self.lock = threading.RLock()
        fin = os.pipe()
        fout = os.pipe()
        ferr = os.pipe()
        cmd_args = self.cgi_docker.create_command(env)
        BayLog.debug("%s Spawn: %s", self.tour, cmd_args)

        self.process = Popen(cmd_args, env=env, stdin=fin[0], stdout=fout[1], stderr=ferr[1])

        os.close(fin[0])
        os.close(fout[1])
        os.close(ferr[1])

        self.std_in = os.fdopen(fin[1], "wb")
        self.std_out = os.fdopen(fout[0], "rb")
        self.std_err = os.fdopen(ferr[0], "rb")

        BayLog.debug("%s PID: %d", self.tour, self.process.pid)

        self.tour.req.set_content_handler(self)

    def depart(self):

        try:
            ###############
            # Handle StdOut
            HttpUtil.parse_message_headers(self.std_out, self.tour.res.headers)

            if BayServer.harbor.trace_header:
                for name in self.tour.res.headers.names():
                    for value in self.tour.res.headers.values(name):
                        BayLog.info("%s CGI: resHeader: %s=%s", self.tour, name, value)

            status = self.tour.res.headers.get("Status")

            if not StringUtil.is_empty(status):
                pos = status.find(" ")

                if pos >= 0:
                    code = int(status[0:pos])
                else:
                    code = int(status)

                self.tour.res.headers.status = code

            def callback(len, resume):
                if resume:
                    self.available = True

            self.tour.res.set_consume_listener(callback)

            self.tour.res.send_headers(self.tour_id)

            while True:
                buf = self.std_out.read(CgiTrain.READ_CHUNK_SIZE)
                if len(buf) == 0:
                    break

                BayLog.trace("%s CGITask: read stdout bytes: len=%d", self.tour, len(buf))

                self.available = self.tour.res.send_content(self.tour_id, buf, 0, len(buf))

                while not self.available:
                    time.sleep(0.1)

            ###############
            # Handle StdErr
            ###############
            while True:
                buf = self.std_err.read(CgiTrain.READ_CHUNK_SIZE)
                if len(buf) == 0:
                    break

                BayLog.warn("%s CGITask: read stderr bytes: %d", self.tour, len(buf))
                BayLog.warn(StringUtil.from_bytes(buf))

            self.tour.res.end_content(self.tour_id)

        except HttpException as e:
            raise e

        except BaseException as e:
            BayLog.error("%s CGITask: Catch error: %s", self.tour, e)
            BayLog.error_e(e)
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, "CGI error")

        finally:
            try:
                self.process.wait()
                self.close_pipes()

                BayLog.trace("%s CGITask: process ended", self.tour)
            except BaseException as e:
                BayLog.error_e(e)

    def on_read_content(self, tur, buf, start, length):
        BayLog.info("%s CGITask:onReadContent: start=%d len=%d", tur, start, length)

        wrote_len = self.std_in.write(buf[start:start + length])
        self.std_in.flush()

        BayLog.info("%s CGITask:onReadContent: wrote=%d", tur, wrote_len)
        tur.req.consumed(Tour.TOUR_ID_NOCHECK, length)

    def on_end_content(self, tur):
        BayLog.trace("%s CGITask:endContent", tur)

        if not TrainRunner.post(self):
            raise HttpException(HttpStatus.SERVICE_UNAVAILABLE, "TourAgents is busy")

    def on_abort(self, tur):
        BayLog.trace("%s CGITask:abort", tur)
        self.close_pipes()

        BayLog.trace("%s KILL PROCESS!: %s", tur, self.process)
        self.process.kill()

        return False  # not aborted immediately

    def close_pipes(self):
        try:
            self.std_in.close()
        except OSError:
            pass

        try:
            self.std_out.close()
        except OSError:
            pass

        try:
            self.std_err.close()
        except OSError:
            pass
