from bayserver_core.agent.letters.letter import Letter
from bayserver_core.common.rudder_state import RudderState


class ErrorLetter(Letter):
    err: Exception

    def __init__(self, st: RudderState, err: Exception):
        super().__init__(st)
        self.err = err