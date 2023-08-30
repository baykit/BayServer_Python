from abc import abstractmethod, ABCMeta
from bayserver_core.docker.docker import Docker

class Reroute(Docker, metaclass=ABCMeta):

    @abstractmethod
    def reroute(self, twn, url):
        pass
