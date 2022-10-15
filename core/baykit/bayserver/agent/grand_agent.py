import os
import selectors
import signal
import threading
from abc import ABCMeta, abstractmethod

from baykit.bayserver import bayserver as bs
from baykit.bayserver.symbol import Symbol
from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.bay_message import BayMessage
from baykit.bayserver.sink import Sink
from baykit.bayserver import mem_usage as mem

from baykit.bayserver.agent.accept_handler import AcceptHandler
from baykit.bayserver.agent.non_blocking_handler import NonBlockingHandler
from baykit.bayserver.agent.spin_handler import SpinHandler
from baykit.bayserver.agent.grand_agent_monitor import GrandAgentMonitor
from baykit.bayserver.taxi.taxi_runner import TaxiRunner
from baykit.bayserver.train.train_runner import TrainRunner

from baykit.bayserver.util.io_util import IOUtil
from baykit.bayserver.util.sys_util import SysUtil




class GrandAgent:

    class GrandAgentLifecycleListener(metaclass=ABCMeta):
        @abstractmethod
        def add(self, agt):
            pass

        @abstractmethod
        def remove(self, agt):
            pass


    #
    # CommandReceiver receives commands from GrandAgentMonitor
    #
    class CommandReceiver:
        def __init__(self, agent, read_fd, write_fd):
            self.agent = agent
            self.read_fd = read_fd
            self.write_fd = write_fd
            self.aborted = False

        def __str__(self):
            return f"ComReceiver#{self.agent.agent_id}"

        def on_pipe_readable(self):
            try:
                cmd = IOUtil.read_int32(self.read_fd)
                if cmd is None:
                    BayLog.debug("%s pipe closed: %d", self, self.read_fd)
                    self.agent.abort()
                else:
                    BayLog.debug("%s receive command %d pipe=%d", self, cmd, self.read_fd)
                    if cmd == GrandAgent.CMD_RELOAD_CERT:
                        self.agent.reload_cert()
                    elif cmd == GrandAgent.CMD_MEM_USAGE:
                        self.agent.print_usage()
                    elif cmd == GrandAgent.CMD_SHUTDOWN:
                        self.agent.shutdown()
                        self.aborted = True
                    elif cmd == GrandAgent.CMD_ABORT:
                        IOUtil.write_int32(self.write_fd, GrandAgent.CMD_OK)
                        self.agent.abort()
                        return
                    else:
                        BayLog.error("Unknown command: %d", cmd)

                    IOUtil.write_int32(self.write_fd, GrandAgent.CMD_OK)

            except IOError as e:
                BayLog.error_e(e, "%s Command thread aborted(end)", self)

            except BaseException as e:
                BayLog.error_e(e)
                BayLog.error_e(e, "%s Command thread aborted(end)", self)


        def abort(self):
            BayLog.debug("%s end", self)
            IOUtil.write_int32(self.write_fd, GrandAgent.CMD_CLOSE)

    SELECT_TIMEOUT_SEC = 10

    CMD_OK = 0
    CMD_CLOSE = 1
    CMD_RELOAD_CERT = 2
    CMD_MEM_USAGE = 3
    CMD_SHUTDOWN = 4
    CMD_ABORT = 5

    #
    # class variables
    #
    agents = []
    listeners = []
    monitors = []
    agent_count = 0
    anchorable_port_map = {}
    unanchorable_port_map = {}
    max_ships = 0
    max_agent_id = 0
    multi_core = False
    finale = False

    def __init__(self, agent_id, max_ships, anchorable, recv_pipe, send_pipe, wakeup_pipe=None):
        self.agent_id = agent_id
        self.anchorable = anchorable

        if anchorable:
            self.accept_handler = AcceptHandler(self, GrandAgent.anchorable_port_map)
        else:
            self.accept_handler = None
        self.spin_handler = SpinHandler(self)
        self.non_blocking_handler = NonBlockingHandler(self)

        if wakeup_pipe is None:
            self.wakeup_pipe = None
            self.wakeup_pipe_no = os.pipe()
            IOUtil.set_non_blocking(self.wakeup_pipe_no[0])
            IOUtil.set_non_blocking(self.wakeup_pipe_no[1])
        else:
            self.wakeup_pipe = wakeup_pipe
            self.wakeup_pipe_no = [wakeup_pipe[0].fileno(), wakeup_pipe[1].fileno()]

        self.select_timeout_sec = GrandAgent.SELECT_TIMEOUT_SEC
        self.max_inbound_ships = max_ships
        self.selector = selectors.DefaultSelector()
        self.aborted = False
        self.unanchorable_transporters = {}
        self.command_receiver = GrandAgent.CommandReceiver(self, recv_pipe[0], send_pipe[1])


    def __str__(self):
        return f"Agt#{self.agent_id}"



    def run(self):
        BayLog.info(BayMessage.get(Symbol.MSG_RUNNING_GRAND_AGENT, self))

        self.selector.register(self.wakeup_pipe_no[0], selectors.EVENT_READ)
        self.selector.register(self.command_receiver.read_fd, selectors.EVENT_READ)

        # Set up unanchorable channel
        if not self.anchorable:
            for ch in GrandAgent.unanchorable_port_map.keys():
                port_dkr = GrandAgent.unanchorable_port_map[ch]
                tp = port_dkr.new_transporter(self, ch)
                self.unanchorable_transporters[ch] = tp
                self.non_blocking_handler.add_channel_listener(ch, tp)
                self.non_blocking_handler.ask_to_start(ch)
                if not self.anchorable:
                    self.non_blocking_handler.ask_to_read(ch)

        busy = True
        try:
            while True:
                try:
                    if self.accept_handler:
                        test_busy = self.accept_handler.ch_count >= self.max_inbound_ships
                        if test_busy != busy:
                            busy = test_busy
                            if busy:
                                self.accept_handler.on_busy()
                            else:
                                self.accept_handler.on_free()

                    if self.aborted:
                        # agent finished
                        BayLog.debug("%s End loop", self)
                        break

                    if not self.spin_handler.is_empty():
                        selkeys = self.selector.select(0)
                    else:
                        selkeys = self.selector.select(self.select_timeout_sec)

                    processed = self.non_blocking_handler.register_channel_ops() > 0

                    if len(selkeys) == 0:
                        processed |= self.spin_handler.process_data();

                    # BayLog.trace("%s Selected keys: %s", self, selkeys)
                    for key, events in selkeys:
                        if key.fd == self.wakeup_pipe_no[0]:
                            # Waked up by ask_to_*
                            self.on_waked_up(key.fileobj)
                        elif key.fd == self.command_receiver.read_fd:
                            self.command_receiver.on_pipe_readable()
                        elif self.accept_handler and self.accept_handler.is_server_socket(key.fileobj):
                            self.accept_handler.on_acceptable(key)
                        else:
                            self.non_blocking_handler.handle_channel(key, events)
                        processed = True

                    if not processed:
                        # timeout check if there is nothing to do
                        self.non_blocking_handler.close_timeout_sockets()
                        self.spin_handler.stop_timeout_spins()

                except Sink as e:
                    raise e

                except KeyboardInterrupt as e:
                    BayLog.error("%s interrupted: %s", self, e)
                    break

                except BaseException as e:
                    BayLog.error("%s error: %s", self, e)
                    BayLog.error_e(e)
                    break

        except BaseException as e:
            raise e

        finally:
            BayLog.debug("Agent end: %d", self.agent_id)
            self.command_receiver.abort()
            for lis in GrandAgent.listeners:
                lis.remove(self)


    def shutdown(self):
        BayLog.debug("%s shutdown", self)
        if self.accept_handler:
            self.accept_handler.shutdown()
        self.aborted = True
        self.wakeup()

    def abort(self):
        BayLog.debug("%s abort", self)
        os._exit(1)

    def reload_cert(self):
        for port in GrandAgent.anchorable_port_map.values():
            if port.secure():
                try:
                    port.secure_docker.reload_cert()
                except BaseException as e:
                    BayLog.error_e(e)

    def print_usage(self):
        # print memory usage
        BayLog.info("Agent#%d MemUsage", self.agent_id)
        mem.MemUsage.get(self.agent_id).print_usage(1)

    def on_waked_up(self, ch):
        BayLog.trace("%s On Waked Up", self)
        try:
            while True:
                if self.wakeup_pipe:
                    # pipe emuration by socket
                    IOUtil.recv_int32(self.wakeup_pipe[0])
                else:
                    # OS pipe
                    IOUtil.read_int32(ch)
        except BlockingIOError as e:
            pass

    def wakeup(self):
        #BayLog.debug("%s Waked Up", self)
        if self.wakeup_pipe:
            # pipe emuration by socket
            IOUtil.send_int32(self.wakeup_pipe[1], 0)
        else:
            # OS pipe
            IOUtil.write_int32(self.wakeup_pipe_no[1], 0)



    ######################################################
    # class methods
    ######################################################
    @classmethod
    def init(cls, count, anchorable_port_map, unanchorable_port_map, max_ships, multi_core):
        GrandAgent.agent_count = count
        GrandAgent.anchorable_port_map = anchorable_port_map
        GrandAgent.unanchorable_port_map = unanchorable_port_map
        GrandAgent.max_ships = max_ships
        GrandAgent.multi_core = multi_core
        if len(GrandAgent.unanchorable_port_map) > 0:
            GrandAgent.add(False)
            GrandAgent.agent_count += 1
        for i in range(count):
            GrandAgent.add(True)


    @classmethod
    def get(cls, id):
        for agt in GrandAgent.agents:
            if agt.agent_id == id:
                return agt
        return None

    @classmethod
    def add(cls, anchorable):
        GrandAgent.max_agent_id += 1
        agt_id = GrandAgent.max_agent_id
        if SysUtil.run_on_windows():
            send_pipe = IOUtil.open_local_pipe()
            recv_pipe = IOUtil.open_local_pipe()
        else:
            send_pipe = os.pipe()
            recv_pipe = os.pipe()
            IOUtil.set_non_blocking(send_pipe[0])
            IOUtil.set_non_blocking(send_pipe[1])
            IOUtil.set_non_blocking(recv_pipe[0])
            IOUtil.set_non_blocking(recv_pipe[1])


        if GrandAgent.multi_core:
            # Agents run on multi core (process mode)

            pid = os.fork()
            if pid == 0:
                # train runners and tax runners run in the new process
                cls.invoke_runners()

                agt = GrandAgent(agt_id, bs.BayServer.harbor.max_ships, anchorable, send_pipe, recv_pipe)
                GrandAgent.agents.append(agt)
                for lis in GrandAgent.listeners:
                    lis.add(agt)

                agent_thread = threading.Thread(target=lambda a: a.run(), args=[agt])
                agent_thread.start()

                if SysUtil.run_on_pycharm():
                    signal.signal(signal.SIGINT, signal.SIG_IGN)

                # Main thread sleeps until agent finished
                agent_thread.join()
                os._exit(0)

            mon = GrandAgentMonitor(agt_id, anchorable, send_pipe, recv_pipe)
            GrandAgent.monitors.append(mon)

        else:
            # Agents run on single core (thread mode)
            cls.invoke_runners()

            # Prepare local pipe on Windows
            if SysUtil.run_on_windows():
                wakeup_pipe = IOUtil.open_local_pipe()
            else:
                wakeup_pipe = None

            def run():
                agt = GrandAgent(agt_id, bs.BayServer.harbor.max_ships, anchorable,
                                 send_pipe, recv_pipe, wakeup_pipe)

                GrandAgent.agents.append(agt)
                for lis in GrandAgent.listeners:
                    lis.add(agt)
                agt.run()

            agent_thread = threading.Thread(target=run)
            agent_thread.start()

            mon = GrandAgentMonitor(agt_id, anchorable, send_pipe, recv_pipe)
            GrandAgent.monitors.append(mon)


    @classmethod
    def reload_cert_all(cls):
        for mon in cls.monitors:
            mon.reload_cert()


    @classmethod
    def restart_all(cls):
        BayLog.debug("Restart...")
        old_monitors = cls.monitors.copy()
        for mon in old_monitors:
            mon.shutdown()

    @classmethod
    def shutdown_all(cls):
        BayLog.debug("Shutdown all")
        cls.finale = True
        for mon in cls.monitors.copy():
            mon.shutdown()


    @classmethod
    def abort_all(cls):
        cls.finale = True
        for mon in cls.monitors.copy():
            mon.abort()
        exit(1)

    @classmethod
    def print_usage_all(cls):
        for mon in cls.monitors:
            mon.print_usage()

    @classmethod
    def add_lifecycle_listener(cls, lis):
        GrandAgent.listeners.append(lis)



    @classmethod
    def agent_aborted(cls, agt_id, anchorable):
        BayLog.debug("Agent aborted %d", agt_id)
        BayLog.info(BayMessage.get(Symbol.MSG_GRAND_AGENT_SHUTDOWN, agt_id))

        # delete agent
        cls.agents = [agt for agt in cls.agents if agt.agent_id != agt_id]

        # delete agent monitor
        cls.monitors = [mon for mon in cls.monitors if mon.agent_id != agt_id]

        if not cls.finale:
            if len(cls.agents) < cls.agent_count:
                cls.add(anchorable)

    #
    # Run train runners and taxi runners inner process
    #   ALl the train runners and taxi runners run in each process (not thread)
    #
    @classmethod
    def invoke_runners(cls):
        TrainRunner.init(bs.BayServer.harbor.train_runners)
        TaxiRunner.init(bs.BayServer.harbor.taxi_runners)






