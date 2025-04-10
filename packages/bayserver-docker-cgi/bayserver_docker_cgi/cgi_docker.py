import os.path
from subprocess import TimeoutExpired

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.docker.harbor import Harbor
from bayserver_core.http_exception import HttpException
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.taxi.taxi_runner import TaxiRunner
from bayserver_core.tour.read_file_taxi import ReadFileTaxi
from bayserver_core.tour.tour import Tour
from bayserver_core.util.cgi_util import CgiUtil
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.sys_util import SysUtil
from bayserver_docker_cgi.cgi_req_content_handler import CgiReqContentHandler
from bayserver_docker_cgi.cgi_std_err_ship import CgiStdErrShip
from bayserver_docker_cgi.cgi_std_out_ship import CgiStdOutShip


class CgiDocker(ClubBase):

    DEFAULT_TIMEOUT_SEC = 60
    interpreter: str
    script_base: str
    doc_root: str
    timeout_sec: int

    def __init__(self):
        super().__init__()
        self.interpreter = None
        self.script_base = None
        self.doc_root = None
        self.timeout_sec = CgiDocker.DEFAULT_TIMEOUT_SEC


    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)


    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "interpreter":
            self.interpreter = kv.value

        elif key == "scriptbase":
            self.script_base = kv.value

        elif key == "docroot":
            self.doc_root = kv.value

        elif key == "timeout":
            self.timeout_sec = int(kv.value)

        else:
            return super().init_key_val(kv)
        return True

    def arrive(self, tur: Tour):

        if tur.req.uri.find("..") >= 0:
            raise HttpException(HttpStatus.FORBIDDEN, tur.req.uri)

        base = self.script_base
        if base is None:
            base = tur.town.location

        if StringUtil.is_empty(base):
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, "%s scriptBase of cgi docker or location of town is not specified.", tur.town)

        root = self.doc_root
        if root is None:
            root = tur.town.location

        if StringUtil.is_empty(root):
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, "$s docRoot of cgi docker or location of town is not specified.", tur.town)

        env = CgiUtil.get_env_hash(tur.town.name, root, base, tur)
        if BayServer.harbor.trace_header:
            for name in env.keys():
                value = env[name]
                BayLog.info("%s cgi: env: %s=%s", tur, name, value)

        file_name = env[CgiUtil.SCRIPT_FILENAME]
        if not os.path.isfile(file_name):
            raise HttpException(HttpStatus.NOT_FOUND, file_name)

        #bufsize = tur.ship.protocol_handler.max_res_packet_data_size()
        bufsize = 1024
        handler = CgiReqContentHandler(self, tur)
        tur.req.set_content_handler(handler)
        handler.start_tour(env)
        fname = "cgi#"


        agt = GrandAgent.get(tur.ship.agent_id)

        if BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_SPIDER:
            mpx = agt.spider_multiplexer
            handler.std_out_rd.set_non_blocking()
            handler.std_err_rd.set_non_blocking()

        elif BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_SPIN:
            def eof_checker():
                try:
                    handler.process.wait(0)
                    return True
                except TimeoutExpired as e:
                    return False

            mpx = agt.spin_multiplexer
            handler.std_out_rd.set_non_blocking()
            handler.std_err_rd.set_non_blocking()

        elif BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_TAXI:
            mpx = agt.taxi_multiplexer

        elif BayServer.harbor.cgi_multiplexer() == Harbor.MULTIPLEXER_TYPE_JOB:
            mpx = agt.job_multiplexer

        else:
            raise Sink()

        handler.multiplexer = mpx
        out_ship = CgiStdOutShip()
        out_tp = PlainTransporter(agt.net_multiplexer, out_ship, False, bufsize, False)
        out_ship.init_std_out(handler.std_out_rd, tur.ship.agent_id, tur, out_tp, handler)

        mpx.add_rudder_state(handler.std_out_rd, RudderState(handler.std_out_rd, out_tp))

        ship_id = out_ship.ship_id

        def callback(length: int, resume: bool):
            if resume:
                out_ship.resume_read(ship_id)

        tur.res.set_res_consume_listener(callback)

        err_ship = CgiStdErrShip()
        err_tp = PlainTransporter(agt.net_multiplexer, err_ship, False, bufsize, False)
        err_ship.init_std_err(handler.std_err_rd, tur.ship.agent_id, handler)
        mpx.add_rudder_state(handler.std_err_rd, RudderState(handler.std_err_rd, err_tp))

        mpx.req_read(handler.std_out_rd)
        mpx.req_read(handler.std_err_rd)


    def create_command(self, env):
        script = env[CgiUtil.SCRIPT_FILENAME]
        if self.interpreter is None:
            command = [script]
        else:
            command = [self.interpreter, script]

        if SysUtil.run_on_windows():
            for i in range(len(command)):
                command[i] = command[i].replace('/', '\\')

        return command
