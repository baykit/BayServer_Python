import time
from abc import ABCMeta, abstractmethod
from time import sleep
from typing import List
from threading import Lock

from bayserver_core.agent import grand_agent as ga
from bayserver_core.agent.multiplexer.multiplexer_base import MultiplexerBase
from bayserver_core.agent.multiplexer.write_unit import WriteUnit
from bayserver_core.agent.timer_handler import TimerHandler
from bayserver_core.bay_log import BayLog
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.util.internet_address import InternetAddress


class SpinMultiplexer(MultiplexerBase, TimerHandler, Multiplexer):

    class Lapper(metaclass=ABCMeta):

        state: RudderState
        last_access: int

        def __init__(self, st: RudderState):
            self.state = st
            self.access()

        def access(self) -> None:
            self.last_access = int(time.time())

        @abstractmethod
        def lap(self) -> bool:
            pass

        @abstractmethod
        def next(self) -> None:
            pass

    class ReadIOLapper(Lapper):

        agent: "ga.GrandAgent"

        def __init__(self, agt: "ga.GrandAgent", st: RudderState):
            super().__init__(st)
            self.agent = agt
            st.rudder.set_non_blocking()

        def lap(self) -> bool:
            spun = False

            try:
                infile = self.state.rudder.key()

                try:
                    read_buf = infile.read(self.buf_size)
                except BlockingIOError as e:
                    BayLog.debug("%s %s", self.agent, e)
                    return True

                if read_buf is None:
                    # Python's bug?
                    read_buf = ""

                eof = False
                if len(read_buf) == 0:
                    # EOF
                    if self.state.eof_checker:
                        eof = self.state.eof_checker()

                    if not eof:
                        BayLog.debug("%s Spin read: No stream data", self)
                        return True
                    else:
                        BayLog.debug("%s Spin read: EOF\\(^o^)/", self)

                self.agent.send_read_letter(read_buf, len(read_buf), None, False)
                return False

            except BaseException as e:
                self.agent.send_error_letter(self.state, e, False)
                return False

        def next(self) -> None:
            pass

    spin_count: int
    running_list: List[Lapper]
    running_list_lock: Lock

    def __init__(self, agt: "ga.GrandAgent"):
        MultiplexerBase.__init__(self, agt)
        self.spin_count = 0
        self.running_list = []
        self.running_list_lock = Lock()
        self.agent.add_timer_handler(self)

    def __str__(self):
        return f"SpnMpx[{self.agent}"


    ######################################################
    # Implements Transporter
    ######################################################

    def req_accept(self, rd: Rudder) -> None:
        raise Sink()

    def req_connect(self, rd: Rudder, adr: InternetAddress) -> None:
        raise Sink()

    def req_read(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        if st is None:
            BayLog.error("%s Invalid rudder  %s", self.agent, rd)
            return

        need_read = False
        with self.running_list_lock:
            if not st.reading:
                need_read = True
                st.reading = True

        if need_read:
            self.next_read(st)

        st.access()

    def req_write(self, rd: Rudder, buf: bytearray, adr: InternetAddress, tag: object, lis) -> None:
        st = self.get_rudder_state(rd)
        if st is None:
            BayLog.error("%s Invalid rudder  %s", self.agent, rd)
            lis()
            return

        unt = WriteUnit(buf, adr, tag, lis)
        with st.write_queue_lock:
            st.write_queue.append(unt)
        st.access()

        need_write = False
        with st.write_queue_lock:
            if not st.writing:
                need_write = True
                st.writing = True

        if need_write:
            self.next_write(st)
        st.access()

    def req_end(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        if st is None:
            return
        st.finale = True
        st.access()


    def req_close(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        self.close_rudder(rd)
        self.agent.send_closed_letter(st, False)
        st.access()

    def shutdown(self) -> None:
        self.wakeup()

    def is_non_blocking(self) -> bool:
        return False

    def use_async_api(self) -> bool:
        return False

    def cancel_read(self, st: RudderState) -> None:
        with st.reading_lock:
            BayLog.debug("%s Reading off %s", self.agent, st.rudder)
            st.reading = False
        self._remove_from_running_list(st)

    def cancel_write(self, st: RudderState) -> None:
        pass

    def next_accept(self, st: RudderState) -> None:
        pass

    def next_read(self, st: RudderState) -> None:
        lpr = SpinMultiplexer.ReadIOLapper(self.agent, st)
        lpr.next()

        self._add_to_running_list(lpr)

    def next_write(self, st: RudderState) -> None:
        pass

    def close_rudder(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        self._remove_from_running_list(st)


    def on_busy(self) -> None:
        BayLog.debug("%s onBusy", self.agent)

    def on_free(self) -> None:
        BayLog.debug("%s onFree aborted=%s", self.agent, self.agent.aborted);
        if self.agent.aborted:
            return



    ######################################################
    # Implements TimerHandler
    ######################################################
    def on_timer(self) -> None:
        self.close_timeout_sockets()


    ######################################################
    # Custom methods
    ######################################################

    def is_empty(self) -> bool:
        return len(self.running_list) == 0


    def process_data(self) -> bool:
        if self.is_empty():
            return False

        all_spun = True

        for i in range(len(self.running_list), 0, -1):
            lpr = self.running_list[i-1]
            st = lpr.state
            spun = lpr.lap()
            st.access()

            all_spun = all_spun and spun

        if all_spun:
            self.spin_count += 1
            if self.spin_count > 10:
                sleep(0.01)
            else:
                self.spin_count = 0

        return True

    ######################################################
    # Private methods
    ######################################################

    def _remove_from_running_list(self, st: RudderState) -> None:
        BayLog.debug("remove: %s", st.rudder)
        with self.running_list_lock:
            self.running_list[:] = [lpr for lpr in self.running_list if lpr.state == st]

    def _add_to_running_list(self, lpr: Lapper) -> None:
        BayLog.debug("add: %s", lpr.state.rudder)
        with self.running_list_lock:
            if not lpr in self.running_list:
                self.running_list.append(lpr)
