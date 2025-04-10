from abc import abstractmethod, ABCMeta
from bayserver_core.docker.docker import Docker
from bayserver_core.docker.town import Town


class Reroute(Docker, metaclass=ABCMeta):

    @abstractmethod
    def reroute(self, twn: Town, url: str) -> str:
        pass
