import os
import pathlib

from bayserver_core import bayserver as bs
from bayserver_core.util.groups import Groups
from bayserver_core.bay_log import BayLog
from bayserver_core.config_exception import ConfigException
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol

from bayserver_core.docker.harbor import Harbor
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.trouble import Trouble

from bayserver_core.util.sys_util import SysUtil
from bayserver_core.util.string_util import StringUtil


class BuiltInHarborDocker(DockerBase, Harbor):
    DEFAULT_MAX_SHIPS = 100
    DEFAULT_GRAND_AGENTS = 0
    DEFAULT_TRAIN_RUNNERS = 8
    DEFAULT_TAXI_RUNNERS = 8
    DEFAULT_WAIT_TIMEOUT_SEC = 120
    DEFAULT_KEEP_TIMEOUT_SEC = 20
    DEFAULT_TOUR_BUFFER_SIZE = 1024 * 1024  # 1M
    DEFAULT_TRACE_HEADER = False
    DEFAULT_CHARSET = "UTF-8"
    DEFAULT_CONTROL_PORT = -1
    DEFAULT_MULTI_CORE = True
    DEFAULT_GZIP_COMP = False
    DEFAULT_FILE_SEND_METHOD = Harbor.FILE_SEND_METHOD_TAXI
    DEFAULT_PID_FILE = "bayserver.pid"

    def __init__(self):
        super().__init__()

        # Default charset
        self.charset = BuiltInHarborDocker.DEFAULT_CHARSET

        # Default locale
        self.locale = None

        # Number of ship agents
        self.grand_agents = BuiltInHarborDocker.DEFAULT_GRAND_AGENTS

        # Number of train runners
        self.train_runners = BuiltInHarborDocker.DEFAULT_TRAIN_RUNNERS

        # Number of taxi runners
        self.taxi_runners = BuiltInHarborDocker.DEFAULT_TAXI_RUNNERS

        # Max count of ships
        self.max_ships = BuiltInHarborDocker.DEFAULT_MAX_SHIPS

        # Socket timeout in seconds
        self.socket_timeout_sec = BuiltInHarborDocker.DEFAULT_WAIT_TIMEOUT_SEC

        # Keep-Alive timeout in seconds
        self.keep_timeout_sec = BuiltInHarborDocker.DEFAULT_KEEP_TIMEOUT_SEC

        # Internal buffer size of Tour
        self.tour_buffer_size = BuiltInHarborDocker.DEFAULT_TOUR_BUFFER_SIZE

        # Trace req/res header flag
        self.trace_header = BuiltInHarborDocker.DEFAULT_TRACE_HEADER

        # Trouble docker
        self.trouble = None

        # Auth groups
        self.groups = Groups()

        # File name to redirect stdout/stderr
        self.redirect_file = None

        # Gzip compression flag
        self.gzip_comp = BuiltInHarborDocker.DEFAULT_GZIP_COMP

        # Port number of signal agent
        self.control_port = BuiltInHarborDocker.DEFAULT_CONTROL_PORT

        # Multi core flag
        self.multi_core = BuiltInHarborDocker.DEFAULT_MULTI_CORE

        # Method to send file
        self.file_send_method = BuiltInHarborDocker.DEFAULT_FILE_SEND_METHOD

        # PID file name
        self.pid_file = BuiltInHarborDocker.DEFAULT_PID_FILE

    ######################
    # Implements Docker
    ######################
    def init(self, bcf, parent):
        super().init(bcf, parent)
        if self.grand_agents <= 0:
            self.grand_agents = SysUtil.processor_count()
        if self.train_runners <= 0:
            self.train_runners = 1
        if self.max_ships <= 0:
            self.max_ships = BuiltInHarborDocker.DEFAULT_MAX_SHIPS

        if self.max_ships <= BuiltInHarborDocker.DEFAULT_MAX_SHIPS:
            self.max_ships = BuiltInHarborDocker.DEFAULT_MAX_SHIPS
            BayLog.warn(BayMessage.get(Symbol.CFG_MAX_SHIPS_IS_TO_SMALL, self.max_ships))

        if self.file_send_method == Harbor.FILE_SEND_METHOD_SELECT and not SysUtil.support_select_file():
            BayLog.warn(BayMessage.get(Symbol.CFG_FILE_SEND_METHOD_SELECT_NOT_SUPPORTED))
            self.file_send_method = Harbor.FILE_SEND_METHOD_TAXI

        if self.file_send_method == Harbor.FILE_SEND_METHOD_SPIN and not SysUtil.support_nonblock_file_read():
            BayLog.warn(BayMessage.get(Symbol.CFG_FILE_SEND_METHOD_SPIN_NOT_SUPPORTED))
            self.file_send_method = Harbor.FILE_SEND_METHOD_TAXI

    #######################
    # Implements DockerBase
    #######################

    def init_docker(self, dkr):
        if isinstance(dkr, Trouble):
            self.trouble = dkr
        else:
            return super().init_docker(dkr)

        return True

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "loglevel":
            BayLog.set_log_level(kv.value)
        elif key == "charset":
            self.charset = kv.value
        elif key == "locale":
            self.locale = kv.value
        elif key == "groups":
            try:
                fname = bs.BayServer.parse_path(kv.value)
                self.groups.init(fname)
            except FileNotFoundError:
                raise ConfigException(kv.file_name, kv.line_no, BayMessage.get(Symbol.CFG_FILE_NOT_FOUND, kv.value))
        elif key == "trains":
            self.train_runners = int(kv.value)
        elif key == "taxis" or key == "taxies":
            self.taxi_runners = int(kv.value)
        elif key == "grandagents":
            self.grand_agents = int(kv.value)
        elif key == "maxships":
            self.max_ships = int(kv.value)
        elif key == "timeout":
            self.socket_timeout_sec = int(kv.value)
        elif key == "keeptimeout":
            self.keep_timeout_sec = int(kv.value)
        elif key == "tourbuffersize":
            self.tour_buffer_size = StringUtil.parse_size(kv.value)
        elif key == "traceheader":
            self.trace_header = StringUtil.parse_bool(kv.value)
        elif key == "redirectfile":
            self.redirect_file = kv.value
        elif key == "controlport":
            self.control_port = int(kv.value)
        elif key == "multicore":
            self.multi_core = StringUtil.parse_bool(kv.value)
        elif key == "gzipcomp":
            self.gzip_comp = StringUtil.parse_bool(kv.value)
        elif key == "sendfilemethod":
            v = kv.value.lower()
            if v == "select":
                self.file_send_method = Harbor.FILE_SEND_METHOD_SELECT
            elif v == "spin":
                self.file_send_method = Harbor.FILE_SEND_METHOD_SPIN
            elif v == "taxi":
                self.file_send_method = Harbor.FILE_SEND_METHOD_TAXI
            else:
                raise ConfigException(kv.file_name, kv.line_no,
                                      BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))

        elif key == "pidfile":
            self.pid_file = kv.value

        else:
            return False

        return True
