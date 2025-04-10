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
from bayserver_core.util.locale import Locale

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
    DEFAULT_NET_MULTIPLEXER = Harbor.MULTIPLEXER_TYPE_SPIDER
    DEFAULT_FILE_MULTIPLEXER = Harbor.MULTIPLEXER_TYPE_TAXI
    DEFAULT_LOG_MULTIPLEXER = Harbor.MULTIPLEXER_TYPE_TAXI
    DEFAULT_CGI_MULTIPLEXER = Harbor.MULTIPLEXER_TYPE_SPIDER
    DEFAULT_RECIPIENT = Harbor.RECIPIENT_TYPE_SPIDER
    DEFAULT_PID_FILE = "bayserver.pid"

    # Default charset
    _charset: str

    # Default locale
    _locale: Locale

    # Number of grand agents
    _grand_agents: int

    # Number of train runners
    _train_runners: int

    # Number of taxi runners
    _taxi_runners: int

    # Max count of watercraft
    _max_ships: int

    # Socket timeout in seconds
    _socket_timeout_sec: int

    # Keep-Alive timeout in seconds
    _keep_timeout_sec: int

    # Internal buffer size of Tour
    _tour_buffer_size: int

    # Trace req/res header flag
    _trace_header: bool

    # Trouble docker
    _trouble: Trouble

    # Auth groups
    _groups: Groups

    # File name to redirect stdout/stderr
    _redirect_file: str

    # Gzip compression flag
    _gzip_comp: bool

    # Port number of signal agent
    _control_port: int

    # Multi core flag
    _multi_core: bool

    # Multiplexer type of network I/O
    _net_multiplexer: int

    # Multiplexer type of file read
    _file_multiplexer: int

    # Multiplexer type of log output
    log_multiplexer: int

    # Multiplexer type of CGI input
    _cgi_multiplexer: int

    # Recipient type
    _recipient: int

    # PID file name
    _pid_file: str

    def __init__(self):
        super().__init__()

        self._charset = BuiltInHarborDocker.DEFAULT_CHARSET
        self._locale = None
        self._grand_agents = BuiltInHarborDocker.DEFAULT_GRAND_AGENTS
        self._train_runners = BuiltInHarborDocker.DEFAULT_TRAIN_RUNNERS
        self._taxi_runners = BuiltInHarborDocker.DEFAULT_TAXI_RUNNERS
        self._max_ships = BuiltInHarborDocker.DEFAULT_MAX_SHIPS
        self._socket_timeout_sec = BuiltInHarborDocker.DEFAULT_WAIT_TIMEOUT_SEC
        self._keep_timeout_sec = BuiltInHarborDocker.DEFAULT_KEEP_TIMEOUT_SEC
        self._tour_buffer_size = BuiltInHarborDocker.DEFAULT_TOUR_BUFFER_SIZE
        self._trace_header = BuiltInHarborDocker.DEFAULT_TRACE_HEADER
        self._trouble = None
        self._groups = Groups()
        self._redirect_file = None
        self._gzip_comp = BuiltInHarborDocker.DEFAULT_GZIP_COMP
        self._control_port = BuiltInHarborDocker.DEFAULT_CONTROL_PORT
        self._net_multiplexer = BuiltInHarborDocker.DEFAULT_NET_MULTIPLEXER
        self._file_multiplexer = BuiltInHarborDocker.DEFAULT_FILE_MULTIPLEXER
        self._log_multiplier = BuiltInHarborDocker.DEFAULT_LOG_MULTIPLEXER
        self._cgi_multiplexer = BuiltInHarborDocker.DEFAULT_CGI_MULTIPLEXER
        self._recipient = BuiltInHarborDocker.DEFAULT_RECIPIENT

        # PID file name
        self._pid_file = BuiltInHarborDocker.DEFAULT_PID_FILE

    ######################
    # Implements Docker
    ######################
    def init(self, bcf, parent):
        super().init(bcf, parent)
        if self._grand_agents <= 0:
            self._grand_agents = SysUtil.processor_count()
        if self._train_runners <= 0:
            self._train_runners = 1
        if self._max_ships <= 0:
            self._max_ships = BuiltInHarborDocker.DEFAULT_MAX_SHIPS

        if self._max_ships <= BuiltInHarborDocker.DEFAULT_MAX_SHIPS:
            self._max_ships = BuiltInHarborDocker.DEFAULT_MAX_SHIPS
            BayLog.warn(BayMessage.get(Symbol.CFG_MAX_SHIPS_IS_TO_SMALL, self._max_ships))

        if self._net_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_TAXI or \
            self._net_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_TRAIN or \
            self._net_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_SPIN or \
            self._net_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_PIGEON:
            BayLog.warn(
                BayMessage.get(Symbol.CFG_NET_MULTIPLEXER_NOT_SUPPORTED,
                               Harbor.get_multiplexer_type_name(self._net_multiplexer),
                               Harbor.get_multiplexer_type_name(BuiltInHarborDocker.DEFAULT_NET_MULTIPLEXER)))
            self._net_multiplexer = BuiltInHarborDocker.DEFAULT_NET_MULTIPLEXER


        if self._file_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_SPIDER and not SysUtil.support_select_file() or \
            self._file_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_SPIN and not SysUtil.support_nonblock_file_read() or \
            self._file_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_TRAIN:

            BayLog.warn(
                BayMessage.get(
                    Symbol.CFG_FILE_MULTIPLEXER_NOT_SUPPORTED,
                    Harbor.get_multiplexer_type_name(self._file_multiplexer),
                    Harbor.get_multiplexer_type_name(BuiltInHarborDocker.DEFAULT_FILE_MULTIPLEXER)))

            self._file_multiplexer = BuiltInHarborDocker.DEFAULT_FILE_MULTIPLEXER

        if self.log_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_SPIDER and not SysUtil.support_select_write_file() or \
            self.log_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_SPIN and not SysUtil.support_nonblock_file_write() or \
            self.log_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_TRAIN:
            BayLog.warn(
                BayMessage.get(
                    Symbol.CFG_LOG_MULTIPLEXER_NOT_SUPPORTED,
                    Harbor.get_multiplexer_type_name(self.log_multiplexer),
                    Harbor.get_multiplexer_type_name(BuiltInHarborDocker.DEFAULT_LOG_MULTIPLEXER)))

            self.log_multiplexer = BuiltInHarborDocker.DEFAULT_LOG_MULTIPLEXER

        if self._cgi_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_SPIN or \
            self._cgi_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_PIGEON:
            BayLog.warn(
                BayMessage.get(
                    Symbol.CFG_CGI_MULTIPLEXER_NOT_SUPPORTED,
                    Harbor.get_multiplexer_type_name(self._cgi_multiplexer),
                    Harbor.get_multiplexer_type_name(BuiltInHarborDocker.DEFAULT_CGI_MULTIPLEXER)))
            self._cgi_multiplexer = BuiltInHarborDocker.DEFAULT_CGI_MULTIPLEXER

        if self._net_multiplexer == BuiltInHarborDocker.MULTIPLEXER_TYPE_SPIDER and self._recipient != BuiltInHarborDocker.RECIPIENT_TYPE_SPIDER:
            BayLog.warn(
                BayMessage.get(
                    Symbol.CFG_NET_MULTIPLEXER_DOES_NOT_SUPPORT_THIS_RECIPIENT,
                    Harbor.get_multiplexer_type_name(self._net_multiplexer),
                    Harbor.get_recipient_type_name(self._recipient),
                    Harbor.get_recipient_type_name(BuiltInHarborDocker.RECIPIENT_TYPE_SPIDER)))

            self._recipient = BuiltInHarborDocker.RECIPIENT_TYPE_SPIDER


    #######################
    # Implements DockerBase
    #######################

    def init_docker(self, dkr):
        if isinstance(dkr, Trouble):
            self._trouble = dkr
        else:
            return super().init_docker(dkr)

        return True

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "loglevel":
            BayLog.set_log_level(kv.value)
        elif key == "charset":
            self._charset = kv.value
        elif key == "locale":
            self._locale = kv.value
        elif key == "groups":
            try:
                fname = bs.BayServer.parse_path(kv.value)
                self._groups.init(fname)
            except FileNotFoundError:
                raise ConfigException(kv.file_name, kv.line_no, BayMessage.get(Symbol.CFG_FILE_NOT_FOUND, kv.value))
        elif key == "trains":
            self._train_runners = int(kv.value)
        elif key == "taxis" or key == "taxies":
            self._taxi_runners = int(kv.value)
        elif key == "grandagents":
            self._grand_agents = int(kv.value)
        elif key == "maxships":
            self._max_ships = int(kv.value)
        elif key == "timeout":
            self._socket_timeout_sec = int(kv.value)
        elif key == "keeptimeout":
            self._keep_timeout_sec = int(kv.value)
        elif key == "tourbuffersize":
            self._tour_buffer_size = StringUtil.parse_size(kv.value)
        elif key == "traceheader":
            self._trace_header = StringUtil.parse_bool(kv.value)
        elif key == "redirectfile":
            self._redirect_file = kv.value
        elif key == "controlport":
            self._control_port = int(kv.value)
        elif key == "multicore":
            self._multi_core = StringUtil.parse_bool(kv.value)
        elif key == "gzipcomp":
            self._gzip_comp = StringUtil.parse_bool(kv.value)
        elif key == "netmultiplexer":
            try:
                self._net_multiplexer = Harbor.get_multiplexer_type(kv.value)
            except Exception:
                raise ConfigException(kv.file_name, kv.line_no,
                                      BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))
        elif key == "filemultiplexer":
            try:
                self._file_multiplexer = Harbor.get_multiplexer_type(kv.value)
            except Exception:
                raise ConfigException(kv.file_name, kv.line_no,
                                      BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))
        elif key == "logmultiplexer":
            try:
                self.log_multiplexer = Harbor.get_multiplexer_type(kv.value)
            except Exception:
                raise ConfigException(kv.file_name, kv.line_no,
                                      BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))
        elif key == "cgimultiplexer":
            try:
                self._cgi_multiplexer = Harbor.get_multiplexer_type(kv.value)
            except Exception:
                raise ConfigException(kv.file_name, kv.line_no,
                                      BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))

        elif key == "pidfile":
            self._pid_file = kv.value

        else:
            return False

        return True

    #######################
    # Implements Harbor
    #######################

    def charset(self) -> str:
        return self._charset

    def locale(self) -> Locale:
        return self._locale

    def grand_agents(self) -> int:
        return self._grand_agents

    def train_runners(self) -> int:
        return self._train_runners

    def taxi_runners(self) -> int:
        return self._taxi_runners

    def max_ships(self) -> int:
        return self._max_ships

    def socket_timeout_sec(self) -> int:
        return self._socket_timeout_sec

    def keep_timeout_sec(self) -> int:
        return self._keep_timeout_sec

    def tour_buffer_size(self) -> int:
        return self._tour_buffer_size

    def trace_header(self) -> bool:
        return self._trace_header

    def trouble(self) -> Trouble:
        return self._trouble

    def groups(self) -> Groups:
        return self._groups

    def redirect_file(self) -> str:
        return self._redirect_file

    def gzip_comp(self) -> bool:
        return self._gzip_comp

    def control_port(self) -> int:
        return self._control_port

    def multi_core(self) -> bool:
        return self._multi_core

    def net_multiplexer(self) -> int:
        return self._net_multiplexer

    def file_multiplexer(self) -> int:
        return self._file_multiplexer

    def log_multiplexer(self) -> int:
        return self._log_multiplier

    def cgi_multiplexer(self) -> int:
        return self._cgi_multiplexer

    def recipient(self) -> int:
        return self._recipient

    def pid_file(self) -> str:
        return self._pid_file


