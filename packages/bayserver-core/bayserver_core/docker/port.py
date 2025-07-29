from abc import ABCMeta, abstractmethod
from typing import List

from bayserver_core.common import inbound_ship as isip
from bayserver_core.docker.city import City
from bayserver_core.docker.docker import Docker
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_core.rudder.rudder import Rudder

from bayserver_core.util.internet_address import InternetAddress

class Port(Docker, metaclass=ABCMeta):

    @abstractmethod
    def protocol(self) -> str:
        pass

    @abstractmethod
    def host(self) -> str:
        pass

    @abstractmethod
    def port(self) -> int:
        pass

    @abstractmethod
    def socket_path(self) -> str:
        pass

    @abstractmethod
    def address(self) -> InternetAddress:
        pass

    @abstractmethod
    def anchored(self) -> bool:
        pass

    @abstractmethod
    def secure(self) -> bool:
        pass

    @abstractmethod
    def timeout_sec(self) -> int:
        pass

    @abstractmethod
    def additional_headers(self) -> List[List[str]]:
        pass

    @abstractmethod
    def cities(self) -> List[City]:
        pass

    @abstractmethod
    def find_city(self, name: str) -> City:
        pass

    @abstractmethod
    def on_connected(self, agt_id: int, rd: Rudder):
        pass

    @abstractmethod
    def return_protocol_handler(self, agt_id: int, proto_hnd: ProtocolHandler):
        pass

    @abstractmethod
    def return_ship(self, sip: "isip.InboundShip"):
        pass

    @abstractmethod
    def self_listen(self) -> bool:
        pass

    @abstractmethod
    def listen(self) -> None:
        pass


