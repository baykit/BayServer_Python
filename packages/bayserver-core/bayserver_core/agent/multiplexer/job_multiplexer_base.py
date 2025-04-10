import os
from typing import Tuple

from bayserver_core.agent import grand_agent as gs
from bayserver_core.agent.multiplexer.multiplexer_base import MultiplexerBase
from bayserver_core import bayserver as bs
from bayserver_core.agent.timer_handler import TimerHandler


class JobMultiplexerBase(MultiplexerBase, TimerHandler):

    anchorable: bool
    pipe: Tuple[int, int]

    def __init__(self, agt: "gs.GrandAgent", anchorable: bool):
        super().__init__(agt)

        self.anchorable = anchorable
        self.agent.add_timer_handler(self)
        self.pipe = os.pipe()


    ######################################################
    # Implements Multiplexer
    ######################################################

    def shutdown(self) -> None:
        self.close_all()

    def on_free(self):
        if self.agent.aborted:
            return

        if self.anchorable:
            for rd in bs.BayServer.anchorable_port_map.keys():
                self.req_accept(rd)

    ######################################################
    # Implements TimerHandler
    ######################################################

    def on_timer(self) -> None:
        self.close_timeout_sockets()