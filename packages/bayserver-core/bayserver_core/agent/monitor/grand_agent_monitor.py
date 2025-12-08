import os
import signal
import socket
import sys
import threading
import time
import traceback
from multiprocessing import Process
from typing import ClassVar, Dict, Optional, List

from bayserver_core import bayserver as bs
from bayserver_core.agent import grand_agent as ga
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.docker.port import Port
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.symbol import Symbol


class GrandAgentMonitor:

    num_agents: ClassVar[int] = 0
    cur_id: ClassVar[int] = 0
    monitors: ClassVar[Dict[int, "GrandAgentMonitor"]] = {}
    finale: ClassVar[bool] = False

    agent_id: int
    self_listen: bool
    rudder: Rudder
    process: Process

    def __init__(self, agt_id: int, self_listen: bool, com_channel: Rudder, process: Process) -> None:
        self.agent_id = agt_id
        self.self_listen = self_listen
        self.rudder = com_channel
        self.process = process

    def __str__(self):
        return f"Monitor#{self.agent_id}"

    def start(self) -> None:
        threading.Thread(target=self.run).start()

    def run(self) -> None:
        try:
            while True:
                buf = self.rudder.read(4)
                if len(buf) == 0:
                    raise EOFError()
                elif len(buf) < 4:
                    raise IOError(f"Cannot read int: nbytes={len(buf)}")

                res = self.buffer_to_int(buf)
                if res == ga.GrandAgent.CMD_CLOSE:
                    BayLog.debug("%s read Close", self)
                    break
                else:
                    BayLog.debug("%s read OK: %d", self, res);

        except Exception as e:
            BayLog.fatal("%s Agent terminated", self)
            BayLog.fatal_e(e, traceback.format_stack())

        self.agent_aborted()


    def shutdown(self):
        BayLog.debug("%s send shutdown command", self)
        self.send(ga.GrandAgent.CMD_SHUTDOWN)

    def abort(self):
        BayLog.debug("%s Send abort command", self)
        self.send(ga.GrandAgent.CMD_ABORT)

    def reload_cert(self):
        BayLog.debug("%s Send reload command", self)
        self.send(ga.GrandAgent.CMD_RELOAD_CERT)

    def print_usage(self):
        BayLog.debug("%s Send mem_usage command", self)
        self.send(ga.GrandAgent.CMD_MEM_USAGE)
        time.sleep(1) # lazy implementation

    def send(self, cmd):
        BayLog.debug("%s send command %s pipe=%s", self, cmd, self.rudder)
        buf = self.int_to_buffer(cmd)
        self.rudder.write(buf)

    def close(self):
        self.rudder.close()

    def agent_aborted(self):
        BayLog.error(BayMessage.get(Symbol.MSG_GRAND_AGENT_SHUTDOWN, self.agent_id))

        if self.process is not None:
            try:
                os.kill(self.process.pid, signal.SIGTERM)
            except BaseException as e:
                BayLog.debug_e(e, traceback.format_stack(),"Error on killing process")
            self.process.join()

        del GrandAgentMonitor.monitors[self.agent_id]

        if not GrandAgentMonitor.finale:
            if len(GrandAgentMonitor.monitors) < GrandAgentMonitor.num_agents:
                try:
                    if not bs.BayServer.harbor.multi_core:
                        ga.GrandAgent.add(-1, self.self_listen)
                    GrandAgentMonitor.add(self.self_listen)
                except BaseException as e:
                    BayLog.error_e(e, traceback.format_stack())

    ########################################
    # Class methods
    ########################################
    @classmethod
    def init(cls, num_agents: int) -> None:
        cls.num_agents = num_agents

    @classmethod
    def add(cls, anchorable: bool, self_listen: Optional[bool] = False, self_listen_port_idx: Optional[int] = -1) -> None:
        cls.cur_id = cls.cur_id + 1
        agt_id = cls.cur_id
        if agt_id > 100:
            BayLog.error("Too many agents started")
            sys.exit(1)

        com_ch = socket.socketpair()
        if bs.BayServer.harbor.multi_core:
            new_argv = bs.BayServer.commandline_args.copy()
            new_argv.append("-agentid=" + str(agt_id))

            chs = []
            if not self_listen:
                for rd in bs.BayServer.anchorable_port_map.keys():
                    chs.append(rd.key())

            p = Process(target=run_child, args=(new_argv, chs, com_ch[1], self_listen_port_idx, ))
            p.start()
        else:
            # Thread mode
            ga.GrandAgent.add(agt_id, anchorable, self_listen, self_listen_port_idx)
            agt = ga.GrandAgent.get(agt_id)

            def run():
                agt.add_command_receiver(SocketRudder(com_ch[1]))
                agt.run()

            agent_thread = threading.Thread(target=run)
            agent_thread.start()
            p = None

        cls.monitors[agt_id] = GrandAgentMonitor(agt_id, self_listen, SocketRudder(com_ch[0]), p)
        cls.monitors[agt_id].start()

    @classmethod
    def reload_cert_all(cls):
        for mon in cls.monitors.values():
            mon.reload_cert()

    @classmethod
    def restart_all(cls):
        old_monitors = cls.monitors.copy().values()

        for mon in old_monitors:
            mon.shutdown()

    @classmethod
    def shutdown_all(cls):
        cls.finale = True
        for mon in cls.monitors.copy().values():
            mon.shutdown()

    @classmethod
    def abort_all(cls):
        cls.finale = True
        for mon in cls.monitors.copy().values():
            mon.abort()
        SystemExit(1)

    @classmethod
    def print_usage_all(cls):
        for mon in cls.monitors.values():
            mon.print_usage()

    @classmethod
    def buffer_to_int(cls, buf: bytes) -> int:
        return int.from_bytes(buf, byteorder='big')

    @classmethod
    def int_to_buffer(cls, val: int) -> bytes:
        return val.to_bytes(4, byteorder='big')

def run_child(argv: List[str], chs: List[int], com_ch: socket.socket, self_listen_port_idx: Optional[int]) -> None:
    bs.BayServer.init_child(chs, com_ch, self_listen_port_idx)
    bs.BayServer.main(argv)
