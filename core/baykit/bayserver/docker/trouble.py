from abc import abstractmethod, ABCMeta
from baykit.bayserver.docker.docker import Docker

class Trouble(Docker):
    GUIDE = 1
    TEXT = 2
    REROUTE = 3

    @abstractmethod
    def find(self, status):
        pass
