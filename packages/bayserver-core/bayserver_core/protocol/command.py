from abc import ABCMeta, abstractmethod

from bayserver_core.util.reusable import Reusable


class Command(Reusable, metaclass=ABCMeta):
    """Base for all protocol command objects (CmdHeader / CmdData /
    CmdSettings / ...). Reusable so a CommandStore can pool instances:
    each rent() returns a Command of the requested type, callers run
    init(...) to set per-frame fields, and a later Return() puts it
    back in the pool. reset() clears any state that would otherwise
    leak into the next rental."""

    @abstractmethod
    def unpack(self, pkt):
        pass

    @abstractmethod
    def pack(self, pkt):
        pass

    @abstractmethod
    def handle(self, handler):
        pass

    def __init__(self, type):
        self.type = type

    def reset(self):
        # Subclasses override to clear per-frame fields. type itself is
        # identity (= which pool bucket the command came from) and must
        # not be cleared.
        pass
