from bayserver_core.agent.letters.letter import Letter
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.rudder.rudder import Rudder


class AcceptedLetter(Letter):
    client_rudder: Rudder

    def __init__(self, st: RudderState, client_rd: Rudder):
        super().__init__(st)
        self.client_rudder = client_rd
