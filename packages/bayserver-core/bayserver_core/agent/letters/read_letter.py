from bayserver_core.agent.letters.letter import Letter
from bayserver_core.common.rudder_state import RudderState


class ReadLetter(Letter):
    n_bytes: int
    address: str

    def __init__(self, st: RudderState, n: int, adr: str):
        super().__init__(st)
        self.n_bytes = n
        self.address = adr