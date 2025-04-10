from abc import ABCMeta, abstractmethod

from bayserver_core.docker.docker import Docker
from bayserver_core.tour.tour import Tour


class Log(Docker, metaclass=ABCMeta):

    @abstractmethod
    def log(self, tour: Tour) -> None:
        pass