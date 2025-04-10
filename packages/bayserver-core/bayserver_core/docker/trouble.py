from abc import abstractmethod, ABCMeta
from bayserver_core.docker.docker import Docker


class Trouble(Docker):
    GUIDE = 1
    TEXT = 2
    REROUTE = 3

    class Command:
        method: int
        target: str

        def __init__(self, method: int, target: str):
            self.method = method
            self.target = target

    @abstractmethod
    def find(self, status: int) -> Command:
        pass
