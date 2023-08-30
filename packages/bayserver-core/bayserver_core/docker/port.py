from abc import ABCMeta, abstractmethod
from bayserver_core.docker.docker import Docker


class Port(Docker, metaclass=ABCMeta):

    @abstractmethod
    def address(self):
        pass

    @abstractmethod
    def check_admitted(self, skt):
        pass

    @abstractmethod
    def find_city(self, name):
        pass

    @abstractmethod
    def new_transporter(self, agt, skt):
        pass

    @abstractmethod
    def check_admitted(self, skt):
        pass

    @abstractmethod
    def return_protocol_handler(self, agt, proto_hnd):
        pass

    @abstractmethod
    def return_ship(self, sip):
        pass
