import abc
from abc import abstractmethod

from bayserver_core.common import rudder_state as rs
from bayserver_core.common.transporter import Transporter
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.util.internet_address import InternetAddress
from bayserver_core.util.data_consume_listener import DataConsumeListener


class Multiplexer(metaclass=abc.ABCMeta):
    @abstractmethod
    def add_rudder_state(self, rd: Rudder, st: "rs.RudderState") -> None:
        pass

    @abstractmethod
    def remove_rudder_state(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def get_rudder_state(self, rd: Rudder) -> "rs.RudderState":
        pass

    @abstractmethod
    def get_transporter(self, rd: Rudder) -> Transporter:
        pass

    @abstractmethod
    def req_accept(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def req_connect(self, rd: Rudder, adr: InternetAddress) -> None:
        pass

    @abstractmethod
    def req_read(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def req_write(self, rd: Rudder, buf: bytearray, adr: InternetAddress, tag: object, lis: DataConsumeListener) -> None:
        pass

    @abstractmethod
    def req_end(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def req_close(self, rd: Rudder) -> None:
        pass

    @abstractmethod
    def cancel_read(self, st: "rs.RudderState") -> None:
        pass

    @abstractmethod
    def cancel_write(self, st: "rs.RudderState") -> None:
        pass

    @abstractmethod
    def next_accept(self, st: "rs.RudderState") -> None:
        pass

    @abstractmethod
    def next_read(self, st: "rs.RudderState") -> None:
        pass

    @abstractmethod
    def next_write(self, st: "rs.RudderState") -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass

    @abstractmethod
    def is_non_blocking(self) -> bool:
        pass

    @abstractmethod
    def use_async_api(self) -> bool:
        pass

    @abstractmethod
    def consume_oldest_unit(self, st: "rs.RudderState") -> bool:
        pass

    @abstractmethod
    def close_rudder(self, st: "rs.RudderState") -> None:
        pass

    @abstractmethod
    def is_busy(self) -> bool:
        pass

    @abstractmethod
    def on_busy(self) -> None:
        pass

    @abstractmethod
    def on_free(self) -> None:
        pass
