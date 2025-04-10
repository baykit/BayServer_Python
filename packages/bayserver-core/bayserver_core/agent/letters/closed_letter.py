from bayserver_core.agent.letters.letter import Letter
from bayserver_core.common.rudder_state import RudderState


class ClosedLetter(Letter):

    def __init__(self, st: RudderState):
        super().__init__(st)