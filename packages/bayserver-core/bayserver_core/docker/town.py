from abc import abstractmethod, ABCMeta
from bayserver_core.docker.docker import Docker

class Town(Docker, metaclass=ABCMeta):

    MATCH_TYPE_MATCHED = 1
    MATCH_TYPE_NOT_MATCHED = 2
    MATCH_TYPE_CLOSE = 3

    @abstractmethod
    def reroute(self, uri):
        pass

    @abstractmethod
    def matches(self, uri):
        pass

    @abstractmethod
    def tour_admitted(self, tur):
        pass
