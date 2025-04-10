import abc
from abc import abstractmethod

from bayserver_core.rudder.rudder import Rudder
from bayserver_core.util.data_consume_listener import DataConsumeListener


class Transporter(metaclass=abc.ABCMeta):

    @abstractmethod
    def init(self) -> None:
        pass

    @abstractmethod
    def is_secure(self) -> bool:
        pass

    @abstractmethod
    def on_connected(self, rd: Rudder) -> int:
        pass

    @abstractmethod
    def on_read(self, rd: Rudder, data: bytearray, adr: str) -> int:
        pass

    @abstractmethod
    def on_error(self, rd: Rudder, error: Exception) -> None:
        pass

    @abstractmethod
    def on_closed(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def req_connect(self, rd: Rudder, adr: str) -> None:
        pass

    @abstractmethod
    def req_read(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def req_write(self, rd: Rudder, data: bytes, adr: str, tag: any, listener: DataConsumeListener) -> None:
        pass

    @abstractmethod
    def req_close(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def check_timeout(self, rd: Rudder, duration_sec: int) -> bool:
        pass

    @abstractmethod
    def get_read_buffer(self) -> int:
        pass

    @abstractmethod
    def print_usage(self, indent: int) -> None:
        pass

