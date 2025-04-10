from threading import Lock
import time
from typing import Dict

from bayserver_core.agent import grand_agent as gs
from bayserver_core.agent.multiplexer.write_unit import WriteUnit
from bayserver_core.bay_log import BayLog
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.common.transporter import Transporter
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.sink import Sink


class MultiplexerBase(Multiplexer):

    agent: "gs.GrandAgent"
    rudders: Dict[object, RudderState]
    rudders_lock: Lock
    lock: Lock
    channel_count: int

    def __init__(self, agt: "gs.GrandAgent"):
        self.agent = agt
        self.rudders = {}
        self.rudders_lock = Lock()
        self.lock = Lock()
        self.channel_count = 0

    def __str__(self):
        return str(self.agent)

    ######################################################
    # Implements Multiplexer
    ######################################################

    def add_rudder_state(self, rd: Rudder, st: RudderState) -> None:
        st.multiplexer = self
        with self.rudders_lock:
            self.rudders[rd.key()] = st
        self.channel_count = self.channel_count + 1
        st.access()

    def remove_rudder_state(self, rd: Rudder) -> None:
        with self.rudders_lock:
            del self.rudders[rd.key()]
        self.channel_count = self.channel_count - 1

    def get_rudder_state(self, rd: Rudder) -> RudderState:
        return self._find_rudder_state_by_key(rd.key())

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
            BayLog.error_e(e)

    def is_busy(self):
        return self.channel_count >= self.agent.max_inbound_ships


    ######################################################
    # Custom methods
    ######################################################

    def _find_rudder_state_by_key(self, key: object) -> RudderState:
        if key in self.rudders.keys():
            return self.rudders[key]
        return None

    def close_timeout_sockets(self):
        if len(self.rudders) == 0:
            return

        close_list = []

        now = time.time()
        for st in self.rudders.values():
            if st.transporter is not None:
                try:
                    duration = int(now - st.last_access_time)
                    if st.transporter.check_timeout(st.rudder, duration):
                        BayLog.debug("%s timeout: rd=%s st=%s", self, st.rudder, st)
                        close_list.append(st)

                except IOError as e:
                    BayLog.error_e(e)
                    close_list.append(st)

        for st in close_list:
            self.req_close(st.rudder)

    def close_all(self) -> None:
        copied = self.rudders.values()

        for st in copied:
            if st.rudder != self.agent.command_receiver.rudder:
                self.close_rudder(st.rudder)
