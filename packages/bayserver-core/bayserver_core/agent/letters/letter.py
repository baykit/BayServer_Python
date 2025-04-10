from bayserver_core.common.rudder_state import RudderState


class Letter:
    state: RudderState

    def __init__(self, state: RudderState):
        self.state = state