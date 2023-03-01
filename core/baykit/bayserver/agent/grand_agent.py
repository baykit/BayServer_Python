import os
import selectors
import socket

import signal
import threading
from abc import ABCMeta, abstractmethod

from baykit.bayserver import bayserver as bs
from baykit.bayserver.symbol import Symbol
from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.bay_message import BayMessage
from baykit.bayserver.sink import Sink
from baykit.bayserver import mem_usage as mem

from baykit.bayserver.agent.command_receiver import CommandReceiver
from baykit.bayserver.agent.accept_handler import AcceptHandler
from baykit.bayserver.agent.non_blocking_handler import NonBlockingHandler
from baykit.bayserver.agent.spin_handler import SpinHandler
from baykit.bayserver.agent.grand_agent_monitor import GrandAgentMonitor


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
    agent_count = 0
    max_ships = 0
    max_agent_id = 0
    multi_core = False

    agents = {}
    listeners = []

    anchorable_port_map = {}
    unanchorable_port_map = {}
    finale = False

    def __init__(self, agent_id, max_ships, anchorable):
        self.agent_id = agent_id
        self.anchorable = anchorable

        if anchorable:
            self.accept_handler = AcceptHandler(self, GrandAgent.anchorable_port_map)
        else:
            self.accept_handler = None
        self.spin_handler = SpinHandler(self)
        self.non_blocking_handler = NonBlockingHandler(self)

        pair = socket.socketpair()
        pair[0].setblocking(False)
        pair[1].setblocking(False)
        self.select_wakeup_pipe = [pair[0], pair[1]]

        self.select_timeout_sec = GrandAgent.SELECT_TIMEOUT_SEC
        self.max_inbound_ships = max_ships
        self.selector = selectors.DefaultSelector()
        self.aborted = False
        self.unanchorable_transporters = {}
        self.command_receiver = None


    def __str__(self):
        return f"Agt#{self.agent_id}"



    def run(self):
        BayLog.info(BayMessage.get(Symbol.MSG_RUNNING_GRAND_AGENT, self))

        self.selector.register(self.select_wakeup_pipe[0], selectors.EVENT_READ)
        self.selector.register(self.command_receiver.communication_channel, selectors.EVENT_READ)

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

                    #BayLog.debug("%s select: %s", self, self.selector.get_map())
                    #for k in self.selector.get_map().keys():
                    #    BayLog.debug("ch: %s", k)
                    if not self.spin_handler.is_empty():
                        selkeys = self.selector.select(0)
                    else:
                        selkeys = self.selector.select(self.select_timeout_sec)
                    #BayLog.debug("%s selected %d keys", self, len(selkeys))
                    #for key in selkeys:
                    #    BayLog.debug("key=%s", key)

                    processed = self.non_blocking_handler.register_channel_ops() > 0

                    if len(selkeys) == 0:
                        processed |= self.spin_handler.process_data();

                    # BayLog.trace("%s Selected keys: %s", self, selkeys)
                    for key, events in selkeys:
                        if key.fd == self.select_wakeup_pipe[0].fileno():
                            # Waked up by ask_to_*
                            self.on_waked_up(key.fileobj)
                        elif key.fd == self.command_receiver.communication_channel.fileno():
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

                except KeyboardInterrupt as e:
                    BayLog.error("%s interrupted: %s", self, e)
                    break

                except Sink as e:
                    raise e

                except BaseException as e:
                    BayLog.error_e(e)
                    break

        except BaseException as e:
            raise e

        finally:
            BayLog.debug("Agent end: %d", self.agent_id)
            self.abort(None, 0)


    def shutdown(self):
        BayLog.debug("%s shutdown", self)
        if self.accept_handler:
            self.accept_handler.shutdown()
        self.abort(None, 0)

    def abort(self, err=None, status=1):
        if err:
            BayLog.fatal("%s abort", self)
            BayLog.fatal_e(err)

        self.command_receiver.end()
        for lis in GrandAgent.listeners:
            lis.remove(self)

        del GrandAgent.agents[self.agent_id]

        if bs.BayServer.harbor.multi_core:
            os._exit(1)
        else:
            self.clean()

        self.aborted = True

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
                IOUtil.recv_int32(self.select_wakeup_pipe[0])
        except BlockingIOError as e:
            pass

    def wakeup(self):
        BayLog.debug("%s Waked Up", self)
        # pipe emuration by socket
        IOUtil.send_int32(self.select_wakeup_pipe[1], 0)

    def run_command_receiver(self, com_channel):
        self.command_receiver = CommandReceiver(self, com_channel)

    ######################################################
    # class methods
    ######################################################
    @classmethod
    def init(cls, agt_ids, anchorable_port_map, unanchorable_port_map, max_ships, multi_core):
        GrandAgent.agent_count = len(agt_ids)
        GrandAgent.anchorable_port_map = anchorable_port_map
        GrandAgent.unanchorable_port_map = unanchorable_port_map
        GrandAgent.max_ships = max_ships
        GrandAgent.multi_core = multi_core

        if bs.BayServer.harbor.multi_core:
            for agt_id in agt_ids:
                GrandAgent.add(agt_id, True)

        if len(GrandAgent.unanchorable_port_map) > 0:
            GrandAgent.add(False)
            GrandAgent.agent_count += 1


    @classmethod
    def get(cls, id):
        return GrandAgent.agents[id]

    @classmethod
    def add(cls, agt_id, anchorable):
        if agt_id == -1:
            agt_id = GrandAgent.max_agent_id + 1

        BayLog.debug("Add agent: id=%d", agt_id)

        if agt_id > GrandAgent.max_agent_id:
            GrandAgent.max_agent_id = agt_id

        agt = GrandAgent(agt_id, bs.BayServer.harbor.max_ships, anchorable)
        cls.agents[agt_id] = agt

        for lis in GrandAgent.listeners:
            lis.add(agt)


    @classmethod
    def add_lifecycle_listener(cls, lis):
        GrandAgent.listeners.append(lis)








