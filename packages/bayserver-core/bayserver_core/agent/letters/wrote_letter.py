from bayserver_core.agent.letters.letter import Letter
from bayserver_core.common.rudder_state import RudderState


class WroteLetter(Letter):
    n_bytes: int
    
    def __init__(self, st: RudderState, n_bytes: int):
        super().__init__(st)
        self.n_bytes = n_bytes