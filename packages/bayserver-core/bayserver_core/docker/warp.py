from abc import ABCMeta, abstractmethod

from bayserver_core.docker.docker import Docker
from bayserver_core.ship.ship import Ship


class Warp(Docker, metaclass=ABCMeta):

    @abstractmethod
    def host(self) -> str:
        pass

    @abstractmethod
    def port(self) -> int:
        pass

    @abstractmethod
    def warp_base(self) -> str:
        pass

    @abstractmethod
    def timeout_sec(self) -> int:
        pass

    @abstractmethod
    def keep(self, warp_ship: Ship) -> None:
        pass

    @abstractmethod
    def on_end_ship(self, warp_ship: Ship) -> None:
        pass