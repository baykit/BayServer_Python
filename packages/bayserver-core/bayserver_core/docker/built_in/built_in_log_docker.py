import os
import os.path

from bayserver_core.agent.transporter.plain_transporter import PlainTransporter
from bayserver_core.agent.transporter.spin_write_transporter import SpinWriteTransporter
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.bayserver import BayServer
from bayserver_core.config_exception import ConfigException

from bayserver_core.agent.grand_agent import GrandAgent

from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.log import Log
from bayserver_core.docker.built_in.log_boat import LogBoat
from bayserver_core.docker.built_in.log_items import LogItems
from bayserver_core.docker.built_in.write_file_taxi import WriteFileTaxi
from bayserver_core.symbol import Symbol
from bayserver_core.util.sys_util import SysUtil


class BuiltInLogDocker(DockerBase, Log):
    class AgentListener(GrandAgent.GrandAgentLifecycleListener):

        def __init__(self, dkr):
            self.log_docker = dkr

        def add(self, agt):
            file_name = f"{self.log_docker.file_prefix}_{agt.agent_id}.{self.log_docker.file_ext}";

            boat = LogBoat()

            if self.log_docker.log_write_method == BuiltInLogDocker.LOG_WRITE_METHOD_SELECT:
                tp = PlainTransporter(False, 0, True)  # write only
                tp.init(agt.non_blocking_handler, open(file_name, "ab"), boat)

            elif self.log_docker.log_write_method == BuiltInLogDocker.LOG_WRITE_METHOD_SPIN:
                tp = SpinWriteTransporter()
                tp.init(agt.spin_handler, open(file_name, "ab"), boat)

            elif self.log_docker.log_write_method == BuiltInLogDocker.LOG_WRITE_METHOD_TAXI:
                tp = WriteFileTaxi()
                tp.init(agt.agent_id, open(file_name, "ab"), boat)

            try:
                boat.init(file_name, tp)
            except IOError as e:
                BayLog.fatal(BayMessage.get(Symbol.INT_CANNOT_OPEN_LOG_FILE, file_name));
                BayLog.fatal_e(e);

            self.log_docker.loggers[agt.agent_id] = boat

        def remove(self, agt):
            del self.log_docker.loggers[agt.agent_id]

    LOG_WRITE_METHOD_SELECT = 1
    LOG_WRITE_METHOD_SPIN = 2
    LOG_WRITE_METHOD_TAXI = 3
    DEFAULT_LOG_WRITE_METHOD = LOG_WRITE_METHOD_TAXI

    # Mapping table for format
    log_item_map = {}

    def __init__(self):
        super().__init__()
        # Log send_file name parts
        self.file_prefix = None
        self.file_ext = None

        # Logger for each agent.
        #    Map of Agent ID => LogBoat
        self.loggers = {}

        # Log format
        self.format = None

        # Log items
        self.log_items = []

        # Log write method
        self.log_write_method = BuiltInLogDocker.DEFAULT_LOG_WRITE_METHOD

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)
        p = elm.arg.rfind('.')
        if p == -1:
            self.file_prefix = elm.arg
            self.file_ext = ""
        else:
            self.file_prefix = elm.arg[0: p]
            self.file_ext = elm.arg[p + 1:]

        if not self.format:
            raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_INVALID_LOG_FORMAT, ""))

        if not os.path.isabs(self.file_prefix):
            self.file_prefix = BayServer.get_location(self.file_prefix)

        log_dir = os.path.dirname(self.file_prefix)
        if not os.path.isdir(log_dir):
            os.mkdir(log_dir)

        # Parse format
        self.compile(self.format, self.log_items, elm.file_name, elm.line_no)

        # Check log write method
        if self.log_write_method == BuiltInLogDocker.LOG_WRITE_METHOD_SELECT and not SysUtil.support_select_file():
            BayLog.warn(BayMessage.get(Symbol.CFG_LOG_WRITE_METHOD_SELECT_NOT_SUPPORTED))
            self.log_write_method = BuiltInLogDocker.LOG_WRITE_METHOD_TAXI

        if self.log_write_method == BuiltInLogDocker.LOG_WRITE_METHOD_SPIN and not SysUtil.support_nonblock_file_write():
            BayLog.warn(BayMessage.get(Symbol.CFG_LOG_WRITE_METHOD_SPIN_NOT_SUPPORTED))
            self.log_write_method = BuiltInLogDocker.LOG_WRITE_METHOD_TAXI

        GrandAgent.add_lifecycle_listener(BuiltInLogDocker.AgentListener(self))

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "format":
            self.format = kv.value
        elif key == "logwritemethod":
            value = kv.value.lower()
            if value == "select":
                self.log_write_method = BuiltInLogDocker.LOG_WRITE_METHOD_SELECT
            elif value == "spin":
                self.log_write_method = BuiltInLogDocker.LOG_WRITE_METHOD_SPIN
            elif value == "taxi":
                self.log_write_method = BuiltInLogDocker.LOG_WRITE_METHOD_TAXI
            else:
                raise ConfigException(kv.file_name, kv.line_no,
                                      BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))

        else:
            return False
        return True

    ######################################################
    # Other methods
    ######################################################

    def log(self, tour):
        sb = []

        for item in self.log_items:

            item = str(item.get_item(tour))
            if not item:
                sb.append("-")
            else:
                sb.append(item)

        # If threre are message to write, write it
        if len(sb) > 0:
            self.get_logger(tour.ship.agent).log(''.join(sb))

    ######################################################
    # Private methods
    ######################################################

    def get_logger(self, agt):
        logger = self.loggers.get(agt.agent_id)
        if logger is None:
            raise KeyError(agt.agent_id)
        return logger

    #
    # Compile format pattern
    #
    def compile(self, format, items, file_name, line_no):
        # Find control code
        pos = format.find('%')
        if pos >= 0:
            text = format[:pos]
            items.append(LogItems.TextItem(text))
            self.compile_ctl(format[pos + 1:], items, file_name, line_no)
        else:
            items.append(LogItems.TextItem(format))

    #
    # Compile format pattern(Control code)
    #
    def compile_ctl(self, string, items, file_name, line_no):
        param = None

        # if exists param
        if string[0] == '{':
            # find close bracket
            pos = string.find('}')
            if pos == -1:
                raise ConfigException(file_name, line_no, BayMessage.get(Symbol.CFG_INVALID_LOG_FORMAT, self.format))

            param = string[1: pos - 1]
            string = string[pos + 1:]

        ctl_char = ""
        error = False

        if len(string) == 0:
            error = True

        if not error:
            # get control char
            ctl_char = string[0:1]
            string = string[1:]

            if ctl_char == ">":
                if len(string) == 0:
                    error = True
                else:
                    ctl_char = string[0:1]
                    string = string[1:]

        fct = None
        if not error:
            fct = BuiltInLogDocker.log_item_map[ctl_char]
            if not fct:
                error = True

        if error:
            ConfigException(file_name, line_no,
                            BayMessage.get(Symbol.CFG_INVALID_LOG_FORMAT,
                                           self.format + " (unknown control code: '%" + ctl_char + "')"))

        item = fct()
        item.init(param)

        self.log_items.append(item)

        self.compile(string, items, file_name, line_no)

    log_item_map["a"] = LogItems.RemoteIpItem
    log_item_map["A"] = LogItems.ServerIpItem
    log_item_map["b"] = LogItems.RequestBytesItem2
    log_item_map["B"] = LogItems.RequestBytesItem1
    log_item_map["c"] = LogItems.ConnectionStatusItem
    log_item_map["e"] = LogItems.NullItem
    log_item_map["h"] = LogItems.RemoteHostItem
    log_item_map["H"] = LogItems.ProtocolItem
    log_item_map["i"] = LogItems.RequestHeaderItem
    log_item_map["l"] = LogItems.RemoteLogItem
    log_item_map["m"] = LogItems.MethodItem
    log_item_map["n"] = LogItems.NullItem
    log_item_map["o"] = LogItems.ResponseHeaderItem
    log_item_map["p"] = LogItems.PortItem
    log_item_map["P"] = LogItems.NullItem
    log_item_map["q"] = LogItems.QueryStringItem
    log_item_map["r"] = LogItems.StartLineItem
    log_item_map["s"] = LogItems.StatusItem
    log_item_map[">s"] = LogItems.StatusItem
    log_item_map["t"] = LogItems.TimeItem
    log_item_map["T"] = LogItems.IntervalItem
    log_item_map["u"] = LogItems.RemoteUserItem
    log_item_map["U"] = LogItems.RequestUrlItem
    log_item_map["v"] = LogItems.ServerNameItem
    log_item_map["V"] = LogItems.NullItem
