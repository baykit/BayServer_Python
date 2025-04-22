from bayserver_core.agent import grand_agent as gs
from bayserver_core.agent.multiplexer.multiplexer_base import MultiplexerBase
from bayserver_core.agent.multiplexer.write_unit import WriteUnit
from bayserver_core.bay_log import BayLog
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink
from bayserver_core.taxi.taxi import Taxi
from bayserver_core.taxi.taxi_runner import TaxiRunner
from bayserver_core.util.internet_address import InternetAddress
from bayserver_core.util.data_consume_listener import DataConsumeListener


class TaxiMultiplexer(MultiplexerBase):

    class TaxiForMpx(Taxi):

        rudder_state: RudderState
        for_read: bool

        def __init__(self, rudder_state: RudderState, for_read: bool):
            super().__init__()
            self.rudder_state = rudder_state
            self.for_read = for_read

        def depart(self):
            if self.for_read:
                self.rudder_state.multiplexer.do_next_read(self.rudder_state)
            else:
                self.rudder_state.multiplexer.do_next_write(self.rudder_state)

        def on_timer(self):
            if self.rudder_state.transporter is not None:
                self.rudder_state.transporter.check_timeout(self.rudder_state.rudder, -1)



    def __init__(self, agt: "gs.GrandAgent"):
        super().__init__(agt)


    def __str__(self):
        return f"TaxiMpx[{self.agent}]"

    ######################################################
    # Implements Multiplexer
    ######################################################

    def req_accept(self, rd: Rudder) -> None:
        raise Sink()

    def req_connect(self, rd: Rudder, adr: InternetAddress) -> None:
        raise Sink()

    def req_read(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        if st is None:
            return

        BayLog.debug("%s reqRead rd=%s state=%s", self.agent, st.rudder, st)
        need_read = False
        with st.reading_lock:
            if not st.reading:
                need_read = True
                st.reading = True

        if need_read:
            self.next_read(st)

        st.access()


    def req_write(self, rd: Rudder, buf: bytearray, adr: InternetAddress, tag: object, lis: DataConsumeListener) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqWrite st=%s", self.agent, st)

        if st is None or st.closed:
            BayLog.warn("%s Channel is closed(callback immediately): %s", self.agent, rd)
            lis()
            return

        unt = WriteUnit(buf, adr, tag, lis)
        with st.write_queue_lock:
            st.write_queue.append(unt)

        need_write = False
        with st.writing_lock:
            if not st.writing:
                need_write = True
                st.writing = True

        if need_write:
            self.next_write(st)

        st.access()


    def req_close(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqClose st=%s", self.agent, st);
        if st is None:
            BayLog.warn("%s channel state not found: %s", self.agent, rd)
            return
        self.close_rudder(st.rudder)
        self.agent.send_closed_letter(st, False)
        st.access()

    def cancel_read(self, st: "rs.RudderState") -> None:
        pass

    def cancel_write(self, st: "rs.RudderState") -> None:
        pass

    def next_accept(self, st: RudderState) -> None:
        raise Sink()

    def next_read(self, st: RudderState) -> None:
        self.next_run(st, True)

    def next_write(self, st: RudderState) -> None:
        self.next_run(st, False)

    def shutdown(self) -> None:
        self.close_all()

    def is_non_blocking(self) -> bool:
        return False

    def is_async_api(self):
        return False

    def use_async_api(self) -> bool:
        return False

    def on_busy(self) -> None:
        raise Sink()

    def on_free(self) -> None:
        raise Sink()

    ######################################################
    # Custom methods
    ######################################################

    def next_run(self, st: RudderState, for_read: bool) -> None:
        BayLog.debug("%s Post next run: %s", self, st)

        TaxiRunner.post(self.agent.agent_id, self.TaxiForMpx(st, for_read))

    def do_next_read(self, st: RudderState) -> None:

        st.access()

        try:
            BayLog.debug("%s Try to Read (rd=%s)", self.agent, st.rudder)
            st.read_buf = st.rudder.read(st.buf_size)

            self.agent.send_read_letter(st, len(st.read_buf), None, True)

        except Exception as e:
            self.agent.send_error_letter(st, e, True)


    def do_next_write(self, st: RudderState) -> None:

        st.access()

        if len(st.write_queue) == 0:
            raise Sink("%s write queue is empty", self)

        try:
            u = st.write_queue[0]
            BayLog.debug("%s Try to write: pkt=%s buflen=%d rd=%s closed=%s", self, u.tag, len(u.buf), st.rudder, st.closed)

            n = 0
            if len(u.buf) >= 0:
                n = st.rudder.write(u.buf)
                u.buf = u.buf[n:]

            BayLog.debug("%s Wrote %d bytes", self, n)
            self.agent.send_wrote_letter(st, n, True)
        except Exception as e:
            self.agent.send_error_letter(st, e, True)
            return

