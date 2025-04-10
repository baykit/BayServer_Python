import os
import os.path
from typing import Dict, List

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.lifecycle_listener import LifecycleListener
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.bayserver import BayServer
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.config_exception import ConfigException
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.built_in.log_item import LogItem
from bayserver_core.docker.built_in.log_items import LogItems
from bayserver_core.docker.harbor import Harbor
from bayserver_core.docker.log import Log
from bayserver_core.rudder.io_rudder import IORudder
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.symbol import Symbol


class BuiltInLogDocker(DockerBase, Log):
    class AgentListener(LifecycleListener):

        log_docker: "BuiltInLogDocker"

        def __init__(self, dkr: "BuiltInLogDocker"):
            self.log_docker = dkr

        def add(self, agt_id: int) -> None:
            file_name = f"{self.log_docker.file_prefix}_{agt_id}.{self.log_docker.file_ext}"
            size = 0
            if os.path.exists(file_name):
                size = os.path.getsize(file_name)
            agt = GrandAgent.get(agt_id)

            try:
                f = open(file_name, "ab")
            except IOError as e:
                BayLog.fatal(BayMessage.get(Symbol.INT_CANNOT_OPEN_LOG_FILE, file_name))
                raise e

            rd = IORudder(f)

            if BayServer.harbor.log_multiplexer() == Harbor.MULTIPLEXER_TYPE_TAXI:
                mpx = agt.taxi_multiplexer

            elif BayServer.harbor.log_multiplexer() == Harbor.MULTIPLEXER_TYPE_SPIN:
                mpx = agt.spin_multiplexer

            elif BayServer.harbor.log_multiplexer() == Harbor.MULTIPLEXER_TYPE_SPIDER:
                mpx = agt.spider_multiplexer

            elif BayServer.harbor.log_multiplexer() == Harbor.MULTIPLEXER_TYPE_JOB:
                mpx = agt.job_multiplexer

            else:
                raise Sink()

            st = RudderState(rd)
            st.bytes_written = size
            mpx.add_rudder_state(rd, st)

            self.log_docker.multiplexers[agt_id] = mpx
            self.log_docker.rudders[agt_id] = rd


        def remove(self, agt_id: int) -> None:
            rd = self.log_docker.rudders[agt_id]
            self.log_docker.multiplexers[agt_id].req_close(rd)
            self.log_docker.multiplexers[agt_id] = None
            self.log_docker.rudders[agt_id] = None

    # Mapping table for format
    log_item_map: Dict[str, object] = {}

    # Log send_file name parts
    file_prefix: str
    file_ext: str

    # Log format
    format: str

    # Log items
    log_items: List[LogItem]

    rudders: Dict[int, Rudder]

    # Multiplexer to write to file
    multiplexers: Dict[int, Multiplexer]


    def __init__(self):
        super().__init__()
        self.file_prefix = None
        self.file_ext = None

        # Logger for each agent.
        #    Map of Agent ID => LogBoat
        self.loggers = {}

        self.format = None

        self.log_items = []
        self.rudders = {}
        self.multiplexers = {}


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

        GrandAgent.add_lifecycle_listener(BuiltInLogDocker.AgentListener(self))

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "format":
            self.format = kv.value

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
            self.multiplexers[tour.ship.agent_id].req_write(
                self.rudders[tour.ship.agent_id],
                bytearray(''.join(sb).encode()),
                None,
                "log",
            None)

    ######################################################
    # Private methods
    ######################################################

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
