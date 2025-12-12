from abc import ABCMeta, abstractmethod
from typing import List

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.tour.tour import Tour


class InboundHandler(metaclass=ABCMeta):

    #
    #  Send protocol error
    #   return true if connection must be closed
    #
    @abstractmethod
    def on_protocol_error(self, e: ProtocolException, stk: List[str]):
        pass

    #
    #  Send HTTP headers to client
    #
    @abstractmethod
    def send_res_headers(self, tur: Tour):
        pass

    #
    # Send Contents to client
    #
    @abstractmethod
    def send_res_content(self, tur: Tour, bytes, ofs: int, length: int, callback):
        pass

    #
    # Send end of contents to client.
    #  sendEnd cannot refer Tour instance because it is discarded before call.
    #
    @abstractmethod
    def send_end_tour(self, tur: Tour, keep_alive: bool, callback):
        pass
