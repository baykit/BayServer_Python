from abc import abstractmethod, ABCMeta
from typing import List

from bayserver_core.docker import city as c
from bayserver_core.docker.club import Club
from bayserver_core.docker.docker import Docker
from bayserver_core.tour.tour import Tour


class Town(Docker, metaclass=ABCMeta):

    MATCH_TYPE_MATCHED = 1
    MATCH_TYPE_NOT_MATCHED = 2
    MATCH_TYPE_CLOSE = 3

    # Get the name (path) of this town
    # The name ends with "/"
    @abstractmethod
    def name(self) -> str:
        pass

    # Get city
    @abstractmethod
    def city(self) -> "c.City":
        pass

    #  Get the physical location of this town
    @abstractmethod
    def location(self) -> str:
        pass

    # Get index file
    @abstractmethod
    def welcome_file(self) -> str:
        pass

    # All clubs in this town
    @abstractmethod
    def clubs(self) -> List[Club]:
        pass



    @abstractmethod
    def reroute(self, uri: str) -> str:
        pass

    @abstractmethod
    def matches(self, uri: str) -> int:
        pass

    @abstractmethod
    def tour_admitted(self, tur: Tour) -> None:
        pass
