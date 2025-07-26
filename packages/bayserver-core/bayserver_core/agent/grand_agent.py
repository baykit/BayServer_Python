import os
import sys
import threading
import time
from argparse import ArgumentError
from typing import ClassVar, List, Dict
from ssl import SSLError

from bayserver_core import bayserver as bs
from bayserver_core import mem_usage as mem
from bayserver_core.agent.command_receiver import CommandReceiver
from bayserver_core.agent.letters.accepted_letter import AcceptedLetter
from bayserver_core.agent.letters.closed_letter import ClosedLetter
from bayserver_core.agent.letters.connected_letter import ConnectedLetter
from bayserver_core.agent.letters.error_letter import ErrorLetter
from bayserver_core.agent.letters.letter import Letter
from bayserver_core.agent.letters.read_letter import ReadLetter
from bayserver_core.agent.letters.wrote_letter import WroteLetter
from bayserver_core.agent.multiplexer.job_multiplexer import JobMultiplexer
from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.agent.multiplexer.spider_multiplexer import SpiderMultiplexer
from bayserver_core.agent.multiplexer.spin_multiplexer import SpinMultiplexer
from bayserver_core.agent.multiplexer.taxi_multiplexer import TaxiMultiplexer
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.timer_handler import TimerHandler
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.postpone import Postpone
from bayserver_core.common.recipient import Recipient
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.docker.harbor import Harbor
from bayserver_core.http_exception import HttpException
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.symbol import Symbol
from bayserver_core.util.internet_address import InternetAddress
from bayserver_core.util.sys_util import SysUtil


class GrandAgent:


    SELECT_TIMEOUT_SEC = 10

    CMD_OK = 0
    CMD_CLOSE = 1
    CMD_RELOAD_CERT = 2
    CMD_MEM_USAGE = 3
    CMD_SHUTDOWN = 4
    CMD_ABORT = 5
    CMD_CATCHUP = 6


    agent_id: int
    anchorable: bool
    net_multiplexer: Multiplexer
    job_multiplexer: Multiplexer
    taxi_multiplexer: Multiplexer
    spin_multiplexer: SpinMultiplexer
    spider_multiplexer: SpiderMultiplexer
    job_multiplexer: Multiplexer
    recipient: Recipient

    max_inbound_ships: int
    aborted: bool
    command_receiver: CommandReceiver
    timer_handlers: List[TimerHandler]
    last_timeout_check: float
    letter_queue: List[Letter]
    letter_queue_lock: threading.Lock
    postpone_queue: List[Postpone]
    postpone_queue_lock: threading.Lock


    #
    # class variables
    #
    agent_count: ClassVar[int] = 0
    max_agent_id: ClassVar[int] = 0
    max_ships: ClassVar[int] = 0

    agents: ClassVar[Dict] = {}
    listeners: ClassVar[List] = []

    finale: ClassVar[bool] = False

    def __init__(self, agent_id, max_ships, anchorable):
        self.agent_id = agent_id
        self.max_inbound_ships = max_ships
        self.anchorable = anchorable
        self.timer_handlers = []
        self.aborted = False
        self.letter_queue = []
        self.letter_queue_lock = threading.Lock()
        self.postpone_queue = []
        self.postpone_queue_lock = threading.Lock()

        self.spider_multiplexer = SpiderMultiplexer(self, anchorable)
        self.spin_multiplexer = SpinMultiplexer(self)
        self.job_multiplexer = JobMultiplexer(self, anchorable)
        self.taxi_multiplexer = TaxiMultiplexer(self)

        if bs.BayServer.harbor.recipient() == Harbor.RECIPIENT_TYPE_SPIDER:
            self.recipient = self.spider_multiplexer

        else:
            raise Sink("Multiplexer not supported: %s", Harbor.get_recipient_type_name(bs.BayServer.harbor.recipient()))



        if bs.BayServer.harbor.net_multiplexer() == Harbor.MULTIPLEXER_TYPE_SPIDER:
            self.net_multiplexer = self.spider_multiplexer

        elif bs.BayServer.harbor.net_multiplexer() == Harbor.MULTIPLEXER_TYPE_JOB:
            self.net_multiplexer = self.job_multiplexer

        else:
            raise Sink("Multiplexer not supported: %s", Harbor.get_multiplexer_type_name(bs.BayServer.harbor.net_multiplexer()))

        self.last_timeout_check = 0


    def __str__(self):
        return f"agt#{self.agent_id}"


    def start(self) -> None:
        th = threading.Thread(target=self.run)
        th.start()

    def run(self) -> None:
        BayLog.info(BayMessage.get(Symbol.MSG_RUNNING_GRAND_AGENT, self))

        if self.net_multiplexer.is_non_blocking():
            self.command_receiver.rudder.set_non_blocking()

        self.net_multiplexer.req_read(self.command_receiver.rudder)

        if self.anchorable:
            # Adds server socket channel of anchorable ports
            for rd in bs.BayServer.anchorable_port_map.keys():
                if self.net_multiplexer.is_non_blocking():
                    rd.set_non_blocking()
                self.net_multiplexer.add_rudder_state(rd, RudderState(rd))

        # Set up unanchorable channel
        if not self.anchorable:
            for rd in bs.BayServer.unanchorable_port_map.keys():
                if self.net_multiplexer.is_non_blocking():
                    rd.set_non_blocking()
                port_dkr = bs.BayServer.unanchorable_port_map[rd]
                port_dkr.on_connected(self.agent_id, rd)

        busy = True
        try:
            while not self.aborted:

                test_busy = self.net_multiplexer.is_busy()
                if test_busy != busy:
                    busy = test_busy
                    if busy:
                        self.net_multiplexer.on_busy()
                    else:
                        self.net_multiplexer.on_free()

                if not self.spin_multiplexer.is_empty():
                    received = self.recipient.receive(False)
                    self.spin_multiplexer.process_data()
                else:
                    received = self.recipient.receive(True)

                if self.aborted:
                    # agent finished
                    BayLog.debug("%s aborted by another thread", self)
                    break

                if self.spin_multiplexer.is_empty and len(self.letter_queue) == 0:
                    # timed out
                    # check per 10 seconds
                    if time.time() - self.last_timeout_check >= 10:
                        self._ring()

                while len(self.letter_queue) > 0:
                    let: Letter = None
                    with self.letter_queue_lock:
                        let = self.letter_queue.pop(0)

                    if isinstance(let, AcceptedLetter):
                        self._on_accepted(let)
                    elif isinstance(let, ConnectedLetter):
                        self._on_connected(let)
                    elif isinstance(let, ReadLetter):
                        self._on_read(let)
                    elif isinstance(let, WroteLetter):
                        self._on_wrote(let)
                    elif isinstance(let, ClosedLetter):
                        self._on_closed(let)
                    elif isinstance(let, ErrorLetter):
                        self._on_error(let)

        except BaseException as e:
            BayLog.fatal_e(e, "%s Fatal Error", self)

        finally:
            BayLog.debug("Agent end: %d", self.agent_id)
            self.shutdown()

    def abort_agent(self) -> None:
        BayLog.fatal("%s abort", self)

        if bs.BayServer.harbor.multi_core:
            os._exit(1)

    def req_shutdown(self) -> None:
        self.aborted = True
        self.recipient.wakeup()


    def print_usage(self):
        # print memory usage
        BayLog.info("Agent#%d MemUsage", self.agent_id)
        BayLog.info(" Python version: %s", sys.version)
        mem_usage = 0
        if not SysUtil.run_on_windows():
            import resource
            if hasattr(resource, 'getrusage'):
                mem_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
                if SysUtil.run_on_mac():
                    mem_usage = mem_usage / 1024.0
                mem_usage = int(mem_usage)
        if mem_usage > 0:
            BayLog.info(" Memory used: %s MBytes", "{:,}".format(mem_usage))
        mem.MemUsage.get(self.agent_id).print_usage(1)



    def add_timer_handler(self, handler):
        self.timer_handlers.append(handler)

    def remove_timer_handler(self, handler):
        self.timer_handlers.remove(handler)

    def add_command_receiver(self, rd: Rudder):
        self.command_receiver = CommandReceiver()
        com_transporter = PlainTransporter(self.net_multiplexer, self.command_receiver, True, 8, False)
        self.command_receiver.init(self.agent_id, rd, com_transporter)
        self.net_multiplexer.add_rudder_state(self.command_receiver.rudder, RudderState(self.command_receiver.rudder, com_transporter))
        BayLog.info("ComRec=%s", self.command_receiver)

    def send_accepted_letter(self, st: RudderState, client_rd: Rudder, wakeup: bool) -> None:
        self._send_letter(AcceptedLetter(st, client_rd),  wakeup)

    def send_connected_letter(self, st: RudderState, wakeup: bool) -> None:
        self._send_letter(ConnectedLetter(st),  wakeup)

    def send_read_letter(self, st: RudderState, n: int, adr: InternetAddress, wakeup: bool) -> None:
        self._send_letter(ReadLetter(st, n, adr),  wakeup)

    def send_wrote_letter(self, st: RudderState, n: int, wakeup: bool) -> None:
        self._send_letter(WroteLetter(st, n),  wakeup)

    def send_closed_letter(self, st: RudderState, wakeup: bool) -> None:
        self._send_letter(ClosedLetter(st),  wakeup)

    def send_error_letter(self, st: RudderState, err: Exception, wakeup: bool) -> None:
        self._send_letter(ErrorLetter(st, err),  wakeup)

    def shutdown(self):
        BayLog.debug("%s shutdown", self)
        if self.aborted:
            return

        for lis in GrandAgent.listeners:
            BayLog.debug("%s remove listener: %s", self, lis)
            lis.remove(self.agent_id)

        self.command_receiver.end()
        del GrandAgent.agents[self.agent_id]

        if bs.BayServer.harbor.multi_core:
            os._exit(1)

        self.agent_id = -1


    def reload_cert(self):
        for port in bs.BayServer.anchorable_port_map.values():
            if port.secure():
                try:
                    port._secure_docker.reload_cert()
                except BaseException as e:
                    BayLog.error_e(e)

    def add_postpone(self, p: Postpone) -> None:
        with self.postpone_queue_lock:
            self.postpone_queue.append(p)

    def count_postpones(self) -> int:
        return len(self.postpone_queue)

    def req_catch_up(self) -> None:
        BayLog.debug("%s Req catchUp", self)
        if self.count_postpones() > 0:
            self.catch_up()
        else:
            try:
                self.command_receiver.send_command_to_monitor(self, GrandAgent.CMD_CATCHUP, False)
            except IOError as e:
                BayLog.error_e(e)
                self.abort_agent()

    def catch_up(self) -> None:
        BayLog.debug("%s catchUp", self)
        with self.postpone_queue_lock:
            if len(self.postpone_queue) > 0:
                r = self.postpone_queue.pop(0)
                r.run()


    ######################################################
    # private methods
    ######################################################

    def _ring(self):
        BayLog.trace("%s Ring", self)

        # Timeout check
        for h in self.timer_handlers:
            h.on_timer()
        self.last_timeout_check = time.time()

    def _send_letter(self, let: Letter, wakeup: bool) -> None:
        with self.letter_queue_lock:
            self.letter_queue.append(let)

        if wakeup:
            self.recipient.wakeup()

    def _on_accepted(self, let: AcceptedLetter) -> None:
        st = let.state
        try:
            p = bs.BayServer.anchorable_port_map[st.rudder]
            p.on_connected(self.agent_id, let.client_rudder)
        except (HttpException, IOError) as e:
            if st.transporter is not None:
                st.transporter.on_error(st.rudder, e)
            else:
                BayLog.error_e(e, "Error on handling accept")
            self._next_action(st, NextSocketAction.CLOSE, False)

        if not self.net_multiplexer.is_busy():
            st.multiplexer.next_accept(st)

    def _on_connected(self, let: ConnectedLetter) -> None:
        st = let.state
        if st.closed:
            BayLog.debug("%s Rudder is already closed: rd=%s", self, st.rudder)
            return

        BayLog.debug("%s connected rd=%s", self, st.rudder)
        next_act = None
        try:
            next_act = st.transporter.on_connected(st.rudder)
            BayLog.debug("%s nextAct=%s", self, next_act)

        except IOError as e:
            st.transporter.on_error(st.rudder, e)
            next_act = NextSocketAction.CLOSE

        if next_act == NextSocketAction.READ:
            # Read more
            st.multiplexer.cancel_write(st)

        self._next_action(st, next_act, False)


    def _on_read(self, let: ReadLetter) -> None:
        st = let.state
        if st.closed:
            BayLog.debug("%s Rudder is already closed: rd=%s", self, st.rudder)
            return

        try:
            BayLog.debug("%s read %d bytes (rd=%s)", self, let.n_bytes, st.rudder)
            st.bytes_read += let.n_bytes

            if let.n_bytes <= 0:
                st.read_buf = b""
                next_act = st.transporter.on_read(st.rudder, b"", let.address)
            else:
                next_act = st.transporter.on_read(st.rudder, st.read_buf, let.address)

        except IOError as e:
            st.transporter.on_error(st.rudder, e)
            next_act = NextSocketAction.CLOSE

        self._next_action(st, next_act, True)


    def _on_wrote(self, let: WroteLetter) -> None:
        st = let.state
        if st.closed:
            BayLog.debug("%s Rudder is already closed: rd=%s", self, st.rudder)
            return

        BayLog.debug("%s wrote %d bytes rd=%s qlen=%d", self, let.n_bytes, st.rudder, len(st.write_queue))
        st.bytes_written += let.n_bytes

        if len(st.write_queue) == 0:
            raise Sink("%s Write queue is empty: rd=%s", self, st.rudder)

        unit = st.write_queue[0]
        if len(unit.buf) > 0:
            BayLog.debug("Could not write enough data buf_len=%d", len(unit.buf))
        else:
            st.multiplexer.consume_oldest_unit(st)

        write_more = True

        with st.writing_lock:
            if len(st.write_queue) == 0:
              write_more = False
              st.writing = False

        if write_more:
            st.multiplexer.next_write(st)
        else:
            if st.finale:
              # close
              BayLog.debug("%s finale return Close", self)
              self._next_action(st, NextSocketAction.CLOSE, False)
            else:
              # Write off
              st.multiplexer.cancel_write(st)


    def _on_closed(self, let: ClosedLetter) -> None:
        st = let.state
        BayLog.debug("%s on closed rd=%s", self, st.rudder)
        if st.closed:
            BayLog.debug("%s Rudder is already closed: rd=%s", self, st.rudder)
            return

        st.multiplexer.remove_rudder_state(st.rudder)

        while st.multiplexer.consume_oldest_unit(st):
            pass

        if st.transporter is not None:
            st.transporter.on_closed(st.rudder)

        st.closed = True
        st.access()


    def _on_error(self, let: ErrorLetter) -> None:
        try:
            raise let.err
        except (IOError, HttpException) as e:
            BayLog.error_e(e)
            self._next_action(let.state, NextSocketAction.CLOSE, False)
        except Exception as e:
            BayLog.fatal_e(e, "Cannot handle error")
            raise e

    def _next_action(self, st: RudderState, act: int, reading: bool) -> None:
        BayLog.debug("%s next action: %s (reading=%s)", self, act, reading)
        cancel = False

        if act == NextSocketAction.CONTINUE:
            if reading:
                st.multiplexer.next_read(st)

        elif act == NextSocketAction.READ:
            st.multiplexer.next_read(st)


        elif act == NextSocketAction.WRITE:
            if reading and self.anchorable:
                cancel = True

        elif act == NextSocketAction.CLOSE:
            if reading:
                cancel = True
            st.multiplexer.req_close(st.rudder)

        elif act == NextSocketAction.SUSPEND:
            if reading:
                cancel = True

        else:
            raise ArgumentError(f"Invalid action: #{act}")


        if cancel:
            st.multiplexer.cancel_read(st)
            with st.reading_lock:
                BayLog.debug("%s Reading off %s", self, st.rudder)
                st.reading = False

        st.access()

    ######################################################
    # class methods
    ######################################################
    @classmethod
    def init(cls, agt_ids, max_ships):
        GrandAgent.agent_count = len(agt_ids)
        GrandAgent.max_ships = max_ships

        if bs.BayServer.harbor.multi_core:
            if len(bs.BayServer.unanchorable_port_map) > 0:
                GrandAgent.add(agt_ids[0], False)
                agt_ids.pop(0)

            for agt_id in agt_ids:
                GrandAgent.add(agt_id, True)



    @classmethod
    def get(cls, id) -> "GrandAgent":
        return GrandAgent.agents[id]

    @classmethod
    def add(cls, agt_id: int, anchorable: bool) -> "GrandAgent":
        if agt_id == -1:
            agt_id = GrandAgent.max_agent_id + 1

        BayLog.debug("Add agent: id=%d", agt_id)

        if agt_id > GrandAgent.max_agent_id:
            GrandAgent.max_agent_id = agt_id

        agt = GrandAgent(agt_id, bs.BayServer.harbor.max_ships(), anchorable)
        cls.agents[agt_id] = agt

        for lis in GrandAgent.listeners:
            lis.add(agt_id)

        return agt


    @classmethod
    def add_lifecycle_listener(cls, lis):
        GrandAgent.listeners.append(lis)








