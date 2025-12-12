import abc
from abc import abstractmethod
from typing import List

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.tour.tour import Tour
from bayserver_core.util.data_consume_listener import DataConsumeListener


class TourHandler(metaclass=abc.ABCMeta):

    # Send HTTP headers to client
    @abstractmethod
    def send_res_headers(self, tur: Tour) -> None:
        pass

    # Send Contents to client
    @abstractmethod
    def send_res_content(self, tur: Tour, buf: bytearray, ofs: int, length: int, lis: DataConsumeListener) -> None:
        pass

    # Send end of contents to client.
    @abstractmethod
    def send_end_tour(self, tur: Tour, keep_alive: bool, lis: DataConsumeListener) -> None:
        pass

    # Send protocol error to client
    @abstractmethod
    def on_protocol_error(self, err: ProtocolException, stk: List[str]):
        pass


