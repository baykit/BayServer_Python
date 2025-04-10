from abc import abstractmethod, ABCMeta
from typing import List

from bayserver_core.common.transporter import Transporter
from bayserver_core.docker.docker import Docker
from bayserver_core.ship.ship import Ship


class Secure(Docker, metaclass=ABCMeta):

    @abstractmethod
    def set_app_protocols(self, protocols: List[str]) -> None:
        pass

    @abstractmethod
    def reload_cert(self) -> None:
        pass

    @abstractmethod
    def new_transporter(self, agt_id: int, ship: Ship, buf_size: int) -> Transporter:
        pass

