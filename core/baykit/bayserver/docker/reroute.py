from abc import abstractmethod, ABCMeta
from baykit.bayserver.docker.docker import Docker

class Reroute(Docker, metaclass=ABCMeta):

    @abstractmethod
    def reroute(self, twn, url):
        pass
