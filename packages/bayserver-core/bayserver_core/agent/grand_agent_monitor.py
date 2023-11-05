import socket
import threading
import time
from multiprocessing import Process
import sys

from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.agent import grand_agent as ga
from bayserver_core.util.io_util import IOUtil

class GrandAgentMonitor:

    num_agents = 0
    cur_id = 0
    monitors = {}
    anchored_port_map = {}
    unanchored_port_map = {}
    finale = False

    def __init__(self, agt_id, anchorable, com_channel):
        self.agent_id = agt_id
        self.anchorable = anchorable
        self.communication_channel = com_channel

    def __str__(self):
        return f"Monitor#{self.agent_id}"

    def on_readable(self):
        try:
            res = IOUtil.recv_int32(self.communication_channel)
            if res is None or res == ga.GrandAgent.CMD_CLOSE:
                BayLog.debug("%s read Close", self)
                self.close()
                GrandAgentMonitor.agent_aborted(self.agent_id, self.anchorable)
            else:
                BayLog.debug("%s read: %d", self, res)
        except BlockingIOError as e:
            BayLog.debug("%s no data", self)

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
        BayLog.debug("%s send command %s pipe=%s", self, cmd, self.communication_channel)
        IOUtil.send_int32(self.communication_channel, cmd)

    def close(self):
        self.communication_channel.close()

    ########################################
    # Class methods
    ########################################
    @classmethod
    def init(cls, num_agents, anchored_port_map, unanchored_port_map):
        cls.num_agents = num_agents
        cls.anchored_port_map = anchored_port_map
        cls.unanchored_port_map = unanchored_port_map

        if unanchored_port_map is not None and len(unanchored_port_map) > 0:
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
                for ch in cls.anchored_port_map.keys():
                    chs.append(ch)
            else:
                for ch in cls.unanchored_port_map.keys():
                    chs.append(ch)

            p = Process(target=run_child, args=(new_argv, chs, com_ch[1],))
            p.start()
        else:
            # Thread mode
            ga.GrandAgent.add(agt_id, anchorable)
            agt = ga.GrandAgent.get(agt_id)
            agt.run_command_receiver(com_ch[1])

            def run():
                agt.run()

            agent_thread = threading.Thread(target=run)
            agent_thread.start()

        cls.monitors[agt_id] = GrandAgentMonitor(agt_id, anchorable, com_ch[0])

    @classmethod
    def agent_aborted(cls, agt_id, anchorable):
        BayLog.error(BayMessage.get(Symbol.MSG_GRAND_AGENT_SHUTDOWN, agt_id))

        del cls.monitors[agt_id]

        if not cls.finale:
            if len(cls.monitors) < cls.num_agents:
                try:
                    if not bs.BayServer.harbor.multi_core:
                        ga.GrandAgent.add(-1, anchorable)
                    cls.add(anchorable)
                except BaseException as e:
                    BayLog.error_e(e)


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



def run_child(argv, chs, com_ch):
    bs.BayServer.init_child(chs, com_ch)
    bs.BayServer.main(argv)
