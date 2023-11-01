import os.path
from subprocess import TimeoutExpired

from bayserver_core.agent.transporter.plain_transporter import PlainTransporter
from bayserver_core.agent.transporter.spin_read_transporter import SpinReadTransporter
from bayserver_core.bay_message import BayMessage
from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.config_exception import ConfigException
from bayserver_docker_cgi.cgi_message import CgiMessage
from bayserver_docker_cgi.cgi_req_content_handler import CgiReqContentHandler
from bayserver_docker_cgi.cgi_std_err_yacht import CgiStdErrYacht
from bayserver_docker_cgi.cgi_std_out_yacht import CgiStdOutYacht
from bayserver_docker_cgi.cgi_symbol import CgiSymbol
from bayserver_core.docker.harbor import Harbor

from bayserver_core.http_exception import HttpException
from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.sink import Sink
from bayserver_core.symbol import Symbol
from bayserver_core.taxi.taxi_runner import TaxiRunner
from bayserver_core.tour.read_file_taxi import ReadFileTaxi

from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.cgi_util import CgiUtil
from bayserver_core.util.sys_util import SysUtil
from bayserver_core.util.io_util import IOUtil


class CgiDocker(ClubBase):

    DEFAULT_PROC_READ_METHOD = Harbor.FILE_SEND_METHOD_TAXI
    DEFAULT_TIMEOUT_SEC = 60

    def __init__(self):
        super().__init__()
        self.interpreter = None
        self.script_base = None
        self.doc_root = None
        self.timeout_sec = CgiDocker.DEFAULT_TIMEOUT_SEC

        # Method to read stdin/stderr
        self.proc_read_method = CgiDocker.DEFAULT_PROC_READ_METHOD

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        if self.proc_read_method == Harbor.FILE_SEND_METHOD_SELECT and not SysUtil.support_select_pipe():
            BayLog.warn(CgiMessage.get(CgiSymbol.CGI_PROC_READ_METHOD_SELECT_NOT_SUPPORTED))
            self.proc_read_method = Harbor.FILE_SEND_METHOD_TAXI

        if self.proc_read_method == Harbor.FILE_SEND_METHOD_SPIN and not SysUtil.support_nonblock_pipe_read():
            BayLog.warn(CgiMessage.get(CgiSymbol.CGI_PROC_READ_METHOD_SPIN_NOT_SUPPORTED))
            self.proc_read_method = Harbor.FILE_SEND_METHOD_TAXI


    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "interpreter":
            self.interpreter = kv.value
        elif key == "scriptbase":
            self.script_base = kv.value
        elif key == "docroot":
            self.doc_root = kv.value
        elif key == "processreadmethod":
            v = kv.value.lower()
            if v == "select":
                self.proc_read_method = Harbor.FILE_SEND_METHOD_SELECT
            elif v == "spin":
                self.proc_read_method = Harbor.FILE_SEND_METHOD_SPIN
            elif v == "taxi":
                self.proc_read_method = Harbor.FILE_SEND_METHOD_TAXI
            else:
                raise ConfigException(kv.file_name, kv.line_no,
                                      BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))
        elif key == "timeout":
            self.timeout_sec = int(kv.value)

        else:
            return super().init_key_val(kv)
        return True

    def arrive(self, tur):

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

        out_yat = CgiStdOutYacht()
        err_yat = CgiStdErrYacht()

        if self.proc_read_method == Harbor.FILE_SEND_METHOD_SELECT:
            IOUtil.set_non_blocking(handler.std_out)
            IOUtil.set_non_blocking(handler.std_err)

            out_tp = PlainTransporter(False, bufsize)
            out_yat.init(tur, out_tp, handler)
            out_tp.init(tur.ship.agent.non_blocking_handler, handler.std_out, out_yat)
            out_tp.open_valve()

            err_tp = PlainTransporter(False, bufsize)
            err_yat.init(tur, handler)
            err_tp.init(tur.ship.agent.non_blocking_handler, handler.std_err, err_yat)
            err_tp.open_valve()

        elif self.proc_read_method == Harbor.FILE_SEND_METHOD_SPIN:
            IOUtil.set_non_blocking(handler.std_out)
            IOUtil.set_non_blocking(handler.std_err)

            def eof_checker():
                try:
                    handler.process.wait(0)
                    return True
                except TimeoutExpired as e:
                    return False

            out_tp = SpinReadTransporter(bufsize)
            out_yat.init(tur, out_tp, handler)
            out_tp.init(tur.ship.agent.spin_handler, out_yat, handler.std_out, -1, self.timeout_sec, eof_checker)
            out_tp.open_valve()

            err_tp = SpinReadTransporter(bufsize)
            err_yat.init(tur, handler)
            err_tp.init(tur.ship.agent.spin_handler, err_yat, handler.std_err, -1, self.timeout_sec, eof_checker)
            err_tp.open_valve()

        elif self.proc_read_method == Harbor.FILE_SEND_METHOD_TAXI:
            out_txi = ReadFileTaxi(tur.ship.agent, bufsize)
            out_yat.init(tur, out_txi, handler)
            out_txi.init(handler.std_out, out_yat)
            if not TaxiRunner.post(tur.ship.agent.agent_id, out_txi):
                raise HttpException(HttpStatus.SERVICE_UNAVAILABLE, "Taxi is busy!")

            err_txi = ReadFileTaxi(tur.ship.agent, bufsize)
            err_yat.init(tur, handler)
            err_txi.init(handler.std_err, err_yat)
            if not TaxiRunner.post(tur.ship.agent.agent_id, err_txi):
                raise HttpException(HttpStatus.SERVICE_UNAVAILABLE, "Taxi is busy!")


        else:
            raise Sink()


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
