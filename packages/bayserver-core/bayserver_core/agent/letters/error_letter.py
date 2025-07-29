from typing import List

from bayserver_core.agent.letters.letter import Letter
from bayserver_core.common.rudder_state import RudderState


class ErrorLetter(Letter):
    err: Exception
    stack: List[str]

    def __init__(self, st: RudderState, err: Exception, stk: List[str]):
        super().__init__(st)
        self.err = err
        self.stack = stk