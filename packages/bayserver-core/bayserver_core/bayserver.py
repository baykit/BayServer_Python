import os
import pathlib
import selectors
import signal
import socket
import sys
import traceback
import shutil
from typing import Dict, List, ClassVar, Optional

from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.rudder.udp_socket_rudder import UdpSocketRudder
from bayserver_core.version import Version
from bayserver_core.bay_log import BayLog
from bayserver_core.mem_usage import MemUsage
from bayserver_core.bay_dockers import BayDockers
from bayserver_core.bay_exception import BayException
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.monitor.grand_agent_monitor import GrandAgentMonitor
from bayserver_core.agent.signal.signal_agent import SignalAgent
from bayserver_core.agent.signal.signal_sender import SignalSender

from bayserver_core.bcf.bcf_element import BcfElement
from bayserver_core.bcf.bcf_parser import BcfParser
from bayserver_core.docker.city import City
from bayserver_core.docker.harbor import Harbor
from bayserver_core.common.inbound_ship_store import InboundShipStore
from bayserver_core.docker.port import Port
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.tour.tour_store import TourStore
from bayserver_core.taxi.taxi_runner import TaxiRunner
from bayserver_core.train.train_runner import TrainRunner
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.locale import Locale
from bayserver_core.util.md5_password import MD5Password
from bayserver_core.util.mimes import Mimes
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.sys_util import SysUtil
from bayserver_core.util.exception_util import ExceptionUtil
from bayserver_core.util.cities import Cities


class BayServer:

    MODE_START = 0
    MODE_STOP = 1
    RELOAD_CERT = 2

    ENV_BAYSERVER_HOME = "BSERV_HOME"
    ENV_BAYSERVER_LIB = "BSERV_LIB"
    ENV_BAYSERVER_PLAN = "BSERV_PLAN"

    # Host name
    my_host_name: ClassVar[str] = None

    # Host address
    my_host_address: ClassVar[str] = None

    # BSERV_HOME directory
    bserv_home: ClassVar[str] = None

    # BSERV_LIB directory
    bserv_lib: ClassVar[str] = None

    # Configuration file name (full path)
    bserv_plan: ClassVar[str] = None

    # Dockers
    dockers: ClassVar[BayDockers] = None

    # Anchorable Port docker
    anchorable_port_map: ClassVar[Dict[SocketRudder, Port]] = {}
    unanchorable_port_map: ClassVar[Dict[SocketRudder, Port]] = {}

    # Harbor docker
    harbor: ClassVar[Harbor] = None

    # BayAgent
    bay_agent: ClassVar[SignalAgent] = None

    # City dockers
    cities: ClassVar[Cities] = Cities()

    # Port docker list
    port_docker_list: ClassVar[List[Port]] = []

    # Software name
    software_name: ClassVar[str] = None

    # Command line arguments
    commandline_args: ClassVar[List[str]] = None

    # for child process mode
    channels: ClassVar[List[socket.socket]] = None
    communication_channel: ClassVar[socket.socket] = None
    self_listen_port_idx: ClassVar[int] = None


    def __init__(self):
        # No instance
        pass

    @classmethod
    def init_child(cls, chs, com_ch: socket.socket, self_listen_port_idx: Optional[int]) -> None:
        cls.channels = chs
        cls.communication_channel = com_ch
        cls.self_listen_port_idx = self_listen_port_idx

    @classmethod
    def is_child(cls):
        return cls.channels is not None

    @classmethod
    def get_version(cls) -> str:
        return Version.VERSION

    @classmethod
    def main(cls, args) -> None:
        cls.commandline_args = args

        # Clear contents from parent process
        cls.anchorable_port_map = {}
        cls.unanchorable_port_map = {}

        cmd = None
        home = os.environ.get(cls.ENV_BAYSERVER_HOME)
        plan = os.environ.get(cls.ENV_BAYSERVER_PLAN)
        mkpass = None
        BayLog.set_full_path(SysUtil.run_on_pycharm())
        agt_id = -1
        init = False

        for arg in args:
            larg = arg.lower()
            if larg == "-start":
                cmd = None
            elif larg == "-stop" or larg == "-shutdown":
                cmd = SignalAgent.COMMAND_SHUTDOWN
            elif larg == "-restartagents":
                cmd = SignalAgent.COMMAND_RESTART_AGENTS
            elif larg == "-reloadcert":
                cmd = SignalAgent.COMMAND_RELOAD_CERT
            elif larg == "-memusage":
                cmd = SignalAgent.COMMAND_MEM_USAGE
            elif larg == "-abort":
                cmd = SignalAgent.COMMAND_ABORT
            elif larg == "-init":
                init = True
            elif larg.startswith("-home="):
                home = arg[6:]
            elif larg.startswith("-plan="):
                plan = arg[6:]
            elif larg.startswith("-mkpass="):
                mkpass = arg[8:]
            elif larg.startswith("-loglevel="):
                BayLog.set_log_level(arg[10:])
            elif larg.startswith("-agentid="):
                agt_id = int(larg[9:])

        if mkpass:
            print(MD5Password.encode(mkpass))
            exit(0)

        cls.get_home(home)
        cls.get_lib()
        if init:
            cls.init()
        else:
            cls.get_plan(plan)
            if cmd is None:
                cls.start(agt_id)
            else:
                SignalSender().send_command(cmd)

    @classmethod
    def get_home(cls, home) -> None:
        if home is not None:
            cls.bserv_home = home
        elif os.getenv(cls.ENV_BAYSERVER_HOME) is not None:
            cls.bserv_home = os.environ[cls.ENV_BAYSERVER_HOME]
        elif StringUtil.is_empty(cls.bserv_home):
            cls.bserv_home = '.'

        BayLog.debug("BayServer Home: %s", cls.bserv_home)

    @classmethod
    def get_plan(cls, plan) -> None:
        if plan is not None:
            cls.bserv_plan = plan
        elif os.getenv(cls.ENV_BAYSERVER_PLAN) is not None:
            cls.bserv_plan = os.environ[cls.ENV_BAYSERVER_PLAN]

        if StringUtil.is_empty(cls.bserv_plan):
            cls.bserv_plan = cls.bserv_home + '/plan/bayserver.plan'

        BayLog.debug("BayServer Plan: " + cls.bserv_plan)

    @classmethod
    def get_lib(cls) -> None:
        cls.bserv_lib = os.getenv(cls.ENV_BAYSERVER_LIB)
        if cls.bserv_lib is None or not os.path.isdir(cls.bserv_lib):
            raise BayException("Library directory is not a directory: %s", cls.bserv_lib)


    @classmethod
    def init(cls) -> None:
        init_dir = os.path.join(cls.bserv_lib, "init")
        BayLog.debug("init directory: %s", init_dir)
        file_list = os.listdir(init_dir)
        for file in file_list:
            shutil.copytree(os.path.join(init_dir, file), os.path.join(cls.bserv_home, file))

    @classmethod
    def start(cls, agt_id) -> None:
        try:
            BayMessage.init(cls.bserv_lib + "/conf/messages", Locale.default())

            cls.dockers = BayDockers()

            cls.dockers.init(cls.bserv_lib + "/conf/dockers.bcf")

            Mimes.init(cls.bserv_lib + "/conf/mimes.bcf")
            HttpStatus.init(cls.bserv_lib + "/conf/httpstatus.bcf")

            # Init stores, memory usage managers
            PacketStore.init()
            ProtocolHandlerStore.init()
            InboundShipStore.init()
            TourStore.init(TourStore.MAX_TOURS)

            if cls.bserv_plan is not None:
                cls.load_plan(cls.bserv_plan)

            if len(cls.port_docker_list) == 0:
                raise BayException(BayMessage.get(Symbol.CFG_NO_PORT_DOCKER))

            redirect_file = cls.harbor.redirect_file()

            if redirect_file is not None:
                if not pathlib.Path(redirect_file).is_absolute():
                    redirect_file = cls.bserv_home + "/" + redirect_file
                f = open(redirect_file, "a")
                sys.stdout = f
                sys.stderr = f

            MemUsage.init()


            if SysUtil.run_on_pycharm():
                def int_handler(sig, stk):
                    print("Trap! Interrupted")
                    GrandAgent.abort_all()

                signal.signal(signal.SIGINT, int_handler)

            BayLog.debug("Command line: %s", cls.commandline_args)

            if agt_id == -1:

                cls.print_version()
                cls.my_host_name = socket.gethostname()
                BayLog.info("Host name    : " + cls.my_host_name)
                cls.parent_start()

            else:
                cls.child_start(agt_id)

            return

            while len(GrandAgentMonitor.monitors) > 0:
                sel = selectors.DefaultSelector()
                mon_map = {}
                for mon in GrandAgentMonitor.monitors.values():
                    BayLog.debug("Monitoring pipe of %s", mon)
                    sel.register(mon.communication_channel, selectors.EVENT_READ)
                    mon_map[mon.communication_channel] = mon

                server_skt = None
                if SignalAgent.signal_agent:
                    server_skt = SignalAgent.signal_agent.server_skt
                    sel.register(server_skt, selectors.EVENT_READ)

                selkeys = sel.select()
                for key, events in selkeys:
                    if server_skt and key.fd == server_skt.fileno():
                        SignalAgent.signal_agent.on_socket_readable()
                    else:
                        mon = mon_map[key.fileobj]
                        mon.on_readable()

            SignalAgent.term()

        except BaseException as e:
            trc = traceback.format_exception_only(type(e), e)
            BayLog.fatal_e(e, traceback.format_stack(), "%s", trc[0].rstrip("\n"))

        exit(1)

    @classmethod
    def open_ports(cls,):
        for dkr in cls.port_docker_list:
            # open port
            adr = dkr.address()

            if not dkr.self_listen():
                if dkr.anchored():
                    # Open TCP port
                    BayLog.info(BayMessage.get(Symbol.MSG_OPENING_TCP_PORT, dkr.host(), dkr.port(), dkr.protocol()))

                    if isinstance(adr, str):
                        try:
                            os.unlink(adr)
                        except IOError:
                            pass
                        skt = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    else:
                        skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                    #if not SysUtil.run_on_windows():
                    skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    skt.setblocking(False)
                    try:
                        skt.bind(adr)
                    except OSError as e:
                        BayLog.error_e(e, traceback.format_stack(), BayMessage.get(Symbol.INT_CANNOT_OPEN_PORT, dkr.host(), dkr.port(),
                                                         ExceptionUtil.message(e)))
                        raise e
                    skt.listen(0)
                    cls.anchorable_port_map[SocketRudder(skt)] = dkr
                else:
                    # Open UDP port
                    BayLog.info(BayMessage.get(Symbol.MSG_OPENING_UDP_PORT, dkr.host(), dkr.port(), dkr.protocol()))
                    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    if not SysUtil.run_on_windows():
                       skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    skt.setblocking(False)
                    try:
                       skt.bind(adr)
                    except OSError as e:
                       BayLog.error_e(e, traceback.format_stack(),
                                      BayMessage.get(Symbol.INT_CANNOT_OPEN_PORT, dkr.host(), dkr.port(),
                                                        ExceptionUtil.message(e)))
                       return

                    cls.unanchorable_port_map[UdpSocketRudder(skt)] = dkr

    @classmethod
    def parent_start(cls):
        BayLog.debug("parent_start")
        cls.open_ports()

        if not cls.harbor.multi_core:
            # Thread mode
            GrandAgent.init(cls.harbor.max_ships())
            cls.invoke_runners()

        for i, dkr in enumerate(cls.port_docker_list):
            if dkr.self_listen():
                GrandAgentMonitor.add(dkr.anchored(), True, i)
            elif not dkr.anchored():
                GrandAgentMonitor.add(False)

        for i in range(0, cls.harbor.grand_agents()):
            GrandAgentMonitor.add(True)

        SignalAgent.init(cls.harbor.control_port())
        cls.create_pid_file(SysUtil.pid())

    @classmethod
    def child_start(cls, agt_id):
        BayLog.debug("Agt#%d child_start", agt_id)
        cls.invoke_runners()

        GrandAgent.init(cls.harbor.max_ships())

        if cls.self_listen_port_idx >= 0:
            port_dkr = cls.port_docker_list[cls.self_listen_port_idx]
            GrandAgent.add(agt_id, port_dkr.anchored(), True, cls.self_listen_port_idx)

        else:
            for skt in cls.channels:
                server_addr = skt.getsockname()
                port_no = -1
                port_path = None
                if not SysUtil.run_on_windows() and skt.family == socket.AF_UNIX:
                    # Unix domain socker
                    unix_domain = True
                    anchorable = True
                    port_path = server_addr
                elif skt.type == socket.SOCK_DGRAM:
                    # UDP Port
                    unix_domain = False
                    anchorable = False
                    port_no = server_addr[1]
                else:
                    # TCP port
                    unix_domain = False
                    anchorable = True
                    port_no = server_addr[1]

                port_dkr = None

                for p in cls.port_docker_list:
                    if unix_domain:
                        if p.socket_path() == port_path:
                            port_dkr = p
                            break
                    else:
                        if p.anchored() == anchorable and p.port() == port_no:
                            port_dkr = p
                            break

                if port_dkr is None:
                    BayLog.fatal("Cannot find port docker: %d", port_no)
                    sys.exit(1)

                if port_dkr.anchored():
                    cls.anchorable_port_map[SocketRudder(skt)] = port_dkr
                else:
                    cls.unanchorable_port_map[UdpSocketRudder(skt)] = port_dkr

            GrandAgent.add(agt_id, anchorable, False, None)

        agt = GrandAgent.get(agt_id)
        agt.add_command_receiver(SocketRudder(cls.communication_channel))
        agt.run()

    @classmethod
    def find_city(cls, name):
        return cls.cities.find_city(name)

    @classmethod
    def load_plan(cls, bserv_plan):
        p = BcfParser()
        doc = p.parse(bserv_plan);

        for obj in doc.content_list:
            if isinstance(obj, BcfElement):
                dkr = cls.dockers.create_docker(obj, None)
                if isinstance(dkr, Port):
                    cls.port_docker_list.append(dkr)
                elif isinstance(dkr, Harbor):
                    cls.harbor = dkr
                elif isinstance(dkr, City):
                    cls.cities.add(dkr)

    @classmethod
    def print_version(cls):
        version = "Version " + cls.get_version()
        while len(version) < 28:
            version = ' ' + version

        print("        ----------------------")
        print("       /     BayServer        \\")
        print("-----------------------------------------------------")
        print(" \\", end="")
        for i in range(47 - len(version)):
            print(" ", end="")

        print(version + "  /")
        print("  \\           Copyright (C) 2021 Yokohama Baykit  /")
        print("   \\                     http://baykit.yokohama  /")
        print("    ---------------------------------------------")





    @classmethod
    def parse_path(cls, val):
        val = cls.get_location(val)

        if not os.path.exists(val):
            raise FileNotFoundError(val)

        return val

    @classmethod
    def get_location(cls, val):
        if not os.path.isabs(val):
            val = cls.bserv_home + "/" + val

        return val

    @classmethod
    def get_software_name(cls):
        if cls.software_name is None:
          cls.software_name = "BayServer/" + cls.get_version()

        return cls.software_name


    @classmethod
    def create_pid_file(cls, pid):
        with open(cls.harbor.pid_file(), "w") as f:
            f.write(str(pid))

    #
    # Run train runners and taxi runners inner process
    #   ALl the train runners and taxi runners run in each process (not thread)
    #
    @classmethod
    def invoke_runners(cls):
        TrainRunner.init(cls.harbor.train_runners())
        TaxiRunner.init(cls.harbor.taxi_runners())


if __name__ == "__main__":
    next

