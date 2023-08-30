from abc import abstractmethod, ABCMeta
from bayserver_core.docker.docker import Docker

class Club(Docker, metaclass=ABCMeta):
    pass

    @abstractmethod
    def matches(self, fname):
        pass

    @abstractmethod
    def arrive(self, tur):
        pass
