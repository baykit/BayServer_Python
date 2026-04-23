import time
import traceback
from typing import Set

from bayserver_core.agent import grand_agent as gs
from bayserver_core.common.write_unit import WriteUnit
from bayserver_core.bay_log import BayLog
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.common.transporter import Transporter
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink


class MultiplexerBase(Multiplexer):

    agent: "gs.GrandAgent"
    rudders: Set[Rudder]
    channel_count: int

    def __init__(self, agt: "gs.GrandAgent"):
        self.agent = agt
        self.rudders = set()
        self.channel_count = 0

    def __str__(self):
        return str(self.agent)

    ######################################################
    # Implements Multiplexer
    ######################################################

    def add_rudder_state(self, rd: Rudder, st: RudderState) -> None:
        BayLog.trace("%s add rd=%s chState=%s", self.agent, rd, st)
        st.multiplexer = self
        rd.state = st
        self.rudders.add(rd)
        self.channel_count = self.channel_count + 1
        st.access()

    def remove_rudder_state(self, rd: Rudder) -> None:
        BayLog.trace("%s remove rd=%s", self.agent, rd)
        rd.state = None
        self.rudders.discard(rd)
        self.channel_count = self.channel_count - 1

    def get_rudder_state(self, rd: Rudder) -> RudderState:
        return rd.state

    def get_transporter(self, rd: Rudder) -> Transporter:
        return self.get_rudder_state(rd).transporter

    def req_end(self, rd: Rudder) -> None:
        raise Sink()

    def req_closing(self, rd: Rudder) -> None:
        raise Sink()

    def consume_oldest_unit(self, st: RudderState) -> bool:
        u: WriteUnit
        with st.write_queue_lock:
            if len(st.write_queue) == 0:
                return False
            u = st.write_queue.pop(0)
        u.done()
        return True

    def close_rudder(self, rd: Rudder) -> None:
        BayLog.debug("%s closeRd %s", self.agent, rd)

        if rd.closed():
            BayLog.debug("%s already closed %s", self.agent, rd)

        try:
            rd.close()
        except IOError as e:
            BayLog.error_e(e, traceback.format_stack())

    def is_busy(self):
        return self.channel_count >= self.agent.max_inbound_ships


    ######################################################
    # Custom methods
    ######################################################

    def close_timeout_sockets(self):
        if not self.rudders:
            return

        now = time.time()
        to_close = []
        for rd in list(self.rudders):
            if rd.closed():
                to_close.append(rd)
                continue

            st = rd.state
            if st is None or st.transporter is None:
                continue

            try:
                duration = int(now - st.last_access_time)
                if self.agent.anchorable and st.transporter.check_timeout(rd, duration):
                    BayLog.debug("%s timeout: rd=%s st=%s", self, rd, st)
                    to_close.append(rd)

            except IOError as e:
                BayLog.error_e(e, traceback.format_stack())
                to_close.append(rd)

        for rd in to_close:
            self.req_close(rd)

    def close_all(self) -> None:
        for rd in list(self.rudders):
            if rd != self.agent.command_receiver.rudder:
                self.close_rudder(rd)
