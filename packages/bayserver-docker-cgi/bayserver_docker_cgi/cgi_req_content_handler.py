import os, time
from subprocess import Popen, TimeoutExpired
from typing import Dict

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.postpone import Postpone
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.docker.harbor import Harbor
from bayserver_core.rudder.fd_rudder import FdRudder
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.tour.req_content_handler import ReqContentHandler

from bayserver_core.tour.tour import Tour

from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.class_util import ClassUtil
from bayserver_core.tour.content_consume_listener import ContentConsumeListener
from bayserver_docker_cgi import cgi_docker as cg
from bayserver_docker_cgi.cgi_std_err_ship import CgiStdErrShip
from bayserver_docker_cgi.cgi_std_out_ship import CgiStdOutShip


class CgiReqContentHandler(ReqContentHandler, Postpone):
    READ_CHUNK_SIZE = 8192

    cgi_docker: "cg.CgiDocker"
    tour: Tour
    tour_id: int
    available: bool
    pid: int
    std_in_rd: Rudder
    std_out_rd: Rudder
    std_err_rd: Rudder
    std_out_closed: bool
    std_err_closed: bool
    last_access: int
    multiplexer: Multiplexer
    env: Dict[str, str]

    def __init__(self, dkr: "cg.CgiDocker", tur: Tour, env: Dict[str, str]):
        self.cgi_docker = dkr
        self.tour = tur
        self.tour_id = tur.tour_id
        self.env = env
        self.available = None
        self.process = None
        self.std_in_rd = None
        self.std_out_rd = None
        self.std_err_rd = None
        self.std_out_closed = True
        self.std_err_closed = True
        self.last_access = None

    def __str__(self):
        return ClassUtil.get_local_name(self.__class__)


    ######################################################
    # Implements Postpone
    ######################################################

    def run(self) -> None:
        self.cgi_docker.sub_wait_count()
        BayLog.info("%s challenge postponed tour", self.tour, self.cgi_docker.get_wait_count())
        self.req_start_tour()

    ######################################################
    # Implements ReqContentHandler
    ######################################################

    def on_read_req_content(self, tur: Tour, buf: bytearray, start: int, length: int, lis: ContentConsumeListener):
        BayLog.debug("%s CGI:onReadReqContent: start=%d len=%d", tur, start, length)

        wrote_len = os.write(self.std_in_rd.key(), buf[start:start + length])

        #BayLog.debug("%s CGI:onReadReqContent: wrote=%d", tur, wrote_len)
        tur.req.consumed(Tour.TOUR_ID_NOCHECK, length, lis)
        self.access()

    def on_end_req_content(self, tur):
        BayLog.debug("%s CGI:endReqContent", tur)
        self.access()

    def on_abort_req(self, tur):
        BayLog.debug("%s CGITask:abortReq", tur)

        if not self.std_out_closed:
            self.multiplexer.req_close(self.std_out_rd)
        if not self.std_err_closed:
            self.multiplexer.req_close(self.std_err_rd)

        if self.process is None:
            BayLog.warn("%s Cannot kill process (pid is null)", tur)
        else:
            BayLog.debug("%s KILL PROCESS!: %s", tur, self.process)
            self.process.kill()

        return False  # not aborted immediately

    ######################################################
    # Other methods
    ######################################################

    def req_start_tour(self):
        if self.cgi_docker.add_process_count():
            BayLog.info("%s start tour: wait count=%d", self.tour, self.cgi_docker.get_wait_count())
            self.start_tour()

        else:
            BayLog.warn("%s Cannot start tour: wait count=%d", self.tour, self.cgi_docker.get_wait_count())
            agt = GrandAgent.get(self.tour.ship.agent_id)
            agt.add_postpone(self)
        self.access()

    def start_tour(self):
        self.available = False

        fin = os.pipe()
        fout = os.pipe()
        ferr = os.pipe()
        cmd_args = self.cgi_docker.create_command(self.env)
        BayLog.debug("%s Spawn: %s", self.tour, cmd_args)

        self.process = Popen(cmd_args, env=self.env, stdin=fin[0], stdout=fout[1], stderr=ferr[1])
        BayLog.debug("%s created process; %s", self.tour, self.process)

        os.close(fin[0])
        os.close(fout[1])
        os.close(ferr[1])

        self.std_in_rd = FdRudder(fin[1])
        self.std_out_rd = FdRudder(fout[0])
        self.std_err_rd = FdRudder(ferr[0])
        BayLog.debug("%s PID: %d", self.tour, self.process.pid)

        self.std_out_closed = False
        self.std_err_closed = False

        agt = GrandAgent.get(self.tour.ship.agent_id)
        #bufsize = tur.ship.protocol_handler.max_res_packet_data_size()
        bufsize = 8192

        if BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_SPIDER:
            mpx = agt.spider_multiplexer
            self.std_out_rd.set_non_blocking()
            self.std_err_rd.set_non_blocking()

        elif BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_SPIN:
            def eof_checker():
                try:
                    self.process.wait(0)
                    return True
                except TimeoutExpired as e:
                    return False

            mpx = agt.spin_multiplexer
            self.std_out_rd.set_non_blocking()
            self.std_err_rd.set_non_blocking()

        elif BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_TAXI:
            mpx = agt.taxi_multiplexer

        elif BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_JOB:
            mpx = agt.job_multiplexer

        else:
            raise Sink()

        self.multiplexer = mpx
        out_ship = CgiStdOutShip()
        out_tp = PlainTransporter(agt.net_multiplexer, out_ship, False, bufsize, False)
        out_ship.init_std_out(self.std_out_rd, self.tour.ship.agent_id, self.tour, out_tp, self)

        mpx.add_rudder_state(self.std_out_rd, RudderState(self.std_out_rd, out_tp))

        ship_id = out_ship.ship_id

        def callback(length: int, resume: bool):
            if resume:
                out_ship.resume_read(ship_id)

        self.tour.res.set_res_consume_listener(callback)

        err_ship = CgiStdErrShip()
        err_tp = PlainTransporter(agt.net_multiplexer, err_ship, False, bufsize, False)
        err_ship.init_std_err(self.std_err_rd, self.tour.ship.agent_id, self)
        mpx.add_rudder_state(self.std_err_rd, RudderState(self.std_err_rd, err_tp))

        mpx.req_read(self.std_out_rd)
        mpx.req_read(self.std_err_rd)


        self.access()

    def on_std_out_closed(self):
        self.std_out_closed = True
        if self.std_out_closed and self.std_err_closed:
            self.process_finished()

    def on_std_err_closed(self):
        self.std_err_closed = True
        if self.std_out_closed and self.std_err_closed:
            self.process_finished()

    def access(self):
        self.last_access = int(time.time())

    def timed_out(self):
        if self.cgi_docker.timeout_sec <= 0:
            return False

        duration_sec = int(time.time()) - self.last_access
        BayLog.debug("%s Check CGI timeout: dur=%d, timeout=%d", self.tour, duration_sec, self.cgi_docker.timeout_sec)
        return duration_sec > self.cgi_docker.timeout_sec

    def process_finished(self):
        BayLog.debug("%s process_finished()", self.tour)

        self.process.wait()

        BayLog.debug("%s CGI Process finished: pid=%d code=%d", self.tour, self.process.pid, self.process.returncode)

        agt_id = self.tour.ship.agent_id

        try:
            if self.process.returncode != 0:
                # Exec failed
                BayLog.error("%s CGI Exec error pid=%d code=%d", self.tour, self.process.pid, self.process.returncode & 0xff)

                self.tour.res.send_error(self.tour_id, HttpStatus.INTERNAL_SERVER_ERROR, "Invalid exit status")
            else:
                self.tour.res.end_res_content(self.tour_id)
        except IOError as e:
            BayLog.error_e(e)

        self.cgi_docker.sub_process_count()
        if self.cgi_docker.get_wait_count() > 0:
            BayLog.warn("agt#%d Catch up postponed process: process wait count=%d", agt_id, self.cgi_docker.get_wait_count())
            agt = GrandAgent.get(agt_id)
            agt.req_catch_up()