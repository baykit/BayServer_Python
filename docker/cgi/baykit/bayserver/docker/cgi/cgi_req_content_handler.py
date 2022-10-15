import os
from subprocess import Popen

from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.tour.req_content_handler import ReqContentHandler

from baykit.bayserver.tour.tour import Tour

from baykit.bayserver.util.http_status import HttpStatus
from baykit.bayserver.util.class_util import ClassUtil


class CgiReqContentHandler(ReqContentHandler):
    READ_CHUNK_SIZE = 8192

    def __init__(self, dkr, tur):
        self.cgi_docker = dkr
        self.tour = tur
        self.tour_id = tur.tour_id
        self.available = None
        self.process = None
        self.std_in = None
        self.std_out = None
        self.std_err = None
        self.std_out_closed = None
        self.std_err_closed = None

    def __str__(self):
        return ClassUtil.get_local_name(self.__class__)

    ######################################################
    # Implements ReqContentHandler
    ######################################################

    def on_read_content(self, tur, buf, start, length):
        BayLog.debug("%s CGI:onReadReqContent: start=%d len=%d", tur, start, length)

        wrote_len = self.std_in.write(buf[start:start + length])
        self.std_in.flush()

        #BayLog.debug("%s CGI:onReadReqContent: wrote=%d", tur, wrote_len)
        tur.req.consumed(Tour.TOUR_ID_NOCHECK, length)

    def on_end_content(self, tur):
        BayLog.debug("%s CGI:endReqContent", tur)

    def on_abort(self, tur):
        BayLog.trace("%s CGITask:abortReq", tur)

        if not self.std_out_closed:
            self.tour.ship.agent.non_blocking_handler.ask_to_close(self.std_out)
        if not self.std_err_closed:
            self.tour.ship.agent.non_blocking_handler.ask_to_close(self.std_err)

        BayLog.trace("%s KILL PROCESS!: %s", tur, self.process)
        self.process.kill()

        return False  # not aborted immediately

    ######################################################
    # Other methods
    ######################################################

    def start_tour(self, env):
        self.available = False

        fin = os.pipe()
        fout = os.pipe()
        ferr = os.pipe()
        cmd_args = self.cgi_docker.create_command(env)
        BayLog.debug("%s Spawn: %s", self.tour, cmd_args)

        self.process = Popen(cmd_args, env=env, stdin=fin[0], stdout=fout[1], stderr=ferr[1])
        BayLog.debug("%s created process; %s", self.tour, self.process)

        os.close(fin[0])
        os.close(fout[1])
        os.close(ferr[1])

        self.std_in = os.fdopen(fin[1], "wb")
        self.std_out = os.fdopen(fout[0], "rb")
        self.std_err = os.fdopen(ferr[0], "rb")

        BayLog.debug("%s PID: %d", self.tour, self.process.pid)

        self.std_out_closed = False
        self.std_err_closed = False

    def on_std_out_closed(self):
        self.std_out_closed = True
        if self.std_out_closed and self.std_err_closed:
            self.process_finished()

    def on_std_err_closed(self):
        self.std_err_closed = True
        if self.std_out_closed and self.std_err_closed:
            self.process_finished()

    def process_finished(self):
        self.process.wait()

        BayLog.debug("CGI Process finished: pid=%d code=%d", self.process.pid, self.process.returncode)

        try:
            if self.process.returncode != 0:
                # Exec failed
                BayLog.error("CGI Exec error pid=%d code=%d", self.process.pid, self.process.returncode & 0xff)

                self.tour.res.send_error(self.tour_id, HttpStatus.INTERNAL_SERVER_ERROR, "Exec failed")
            else:
                self.tour.res.end_content(self.tour_id)
        except IOError as e:
            BayLog.error_e(e)