from abc import ABCMeta, abstractmethod
from typing import List

from bayserver_core.docker.club import Club
from bayserver_core.docker.docker import Docker
from bayserver_core.docker.town import Town
from bayserver_core.docker.trouble import Trouble
from bayserver_core.tour.tour import Tour


class City(Docker, metaclass=ABCMeta):

    # City name (host name)
    @abstractmethod
    def name(self) -> str:
        pass

    # All clubs (not included in town) in this city
    @abstractmethod
    def clubs(self) -> List[Club]:
        pass

    # All towns in this city
    @abstractmethod
    def towns(self) -> List[Town]:
        pass

    # Enter city
    @abstractmethod
    def enter(self, tour: Tour) -> None:
        pass

    # Get trouble docker
    @abstractmethod
    def get_trouble(self) -> Trouble:
        pass

    # Logging
    @abstractmethod
    def log(self, tour: Tour) -> None:
        pass