import os
import signal
import socket
import sys
import threading
import time
from multiprocessing import Process
from typing import ClassVar, Dict

from bayserver_core import bayserver as bs
from bayserver_core.agent import grand_agent as ga
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.symbol import Symbol


class GrandAgentMonitor:

    num_agents: ClassVar[int] = 0
    cur_id: ClassVar[int] = 0
    monitors: ClassVar[Dict[int, "GrandAgentMonitor"]] = {}
    finale: ClassVar[bool] = False

    agent_id: int
    anchorable: bool
    rudder: Rudder
    process: Process

    def __init__(self, agt_id: int, anchorable: bool, com_channel: Rudder, process: Process) -> None:
        self.agent_id = agt_id
        self.anchorable = anchorable
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
                if len(buf) < 4:
                    raise IOError("Cannot read int: nbytes=#{n}")

                res = self.buffer_to_int(buf)
                if res == ga.GrandAgent.CMD_CLOSE:
                    BayLog.debug("%s read Close", self)
                    break
                else:
                    BayLog.debug("%s read OK: %d", self, res);

        except Exception as e:
            BayLog.fatal("%s Agent terminated", self)
            BayLog.fatal_e(e)

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
                BayLog.debug_e(e, "Error on killing process")
            self.process.join()

        del GrandAgentMonitor.monitors[self.agent_id]

        if not GrandAgentMonitor.finale:
            if len(GrandAgentMonitor.monitors) < GrandAgentMonitor.num_agents:
                try:
                    if not bs.BayServer.harbor.multi_core:
                        ga.GrandAgent.add(-1, self.anchorable)
                    GrandAgentMonitor.add(self.anchorable)
                except BaseException as e:
                    BayLog.error_e(e)

    ########################################
    # Class methods
    ########################################
    @classmethod
    def init(cls, num_agents):
        cls.num_agents = num_agents

        if len(bs.BayServer.unanchorable_port_map) > 0:
            cls.add(False)
            cls.num_agents += 1

        for i in range(0, num_agents):
            cls.add(True)

    @classmethod
    def add(cls, anchorable):
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
            if anchorable:
                for rd in bs.BayServer.anchorable_port_map.keys():
                    chs.append(rd.key())
            else:
                for rd in bs.BayServer.unanchorable_port_map.keys():
                    chs.append(rd.key())

            p = Process(target=run_child, args=(new_argv, chs, com_ch[1],))
            p.start()
        else:
            # Thread mode
            ga.GrandAgent.add(agt_id, anchorable)
            agt = ga.GrandAgent.get(agt_id)

            def run():
                agt.add_command_receiver(SocketRudder(com_ch[1]))
                agt.run()

            agent_thread = threading.Thread(target=run)
            agent_thread.start()
            p = None

        cls.monitors[agt_id] = GrandAgentMonitor(agt_id, anchorable, SocketRudder(com_ch[0]), p)
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

def run_child(argv, chs, com_ch):
    bs.BayServer.init_child(chs, com_ch)
    bs.BayServer.main(argv)
