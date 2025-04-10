from abc import ABCMeta, abstractmethod

from bayserver_core.docker.docker import Docker
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.tour.tour import Tour


class Permission(Docker, metaclass=ABCMeta):

    @abstractmethod
    def socket_admitted(self, rd: SocketRudder) -> None:
        pass

    @abstractmethod
    def tour_admitted(self, tour: Tour) -> None:
        pass