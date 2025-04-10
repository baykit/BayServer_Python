from abc import ABCMeta, abstractmethod

from bayserver_core.common.warp_data import WarpData
from bayserver_core.tour.tour import Tour

from bayserver_core.util.data_consume_listener import DataConsumeListener

# interface
class WarpHandler(metaclass=ABCMeta):

    @abstractmethod
    def next_warp_id(self) -> int:
        pass

    @abstractmethod
    def new_warp_data(self, warp_id: int) -> WarpData:
        pass

    @abstractmethod
    def send_req_headers(self, tur: Tour) -> None:
        pass

    @abstractmethod
    def send_req_contents(self, tur: Tour, buf: bytearray, start: int, length: int, lis: DataConsumeListener):
        pass

    @abstractmethod
    def send_end_req(self, tur: Tour, keep_alive: bool, lis: DataConsumeListener):
        pass

    #
    # Verify if protocol is allowed
    #
    @abstractmethod
    def verify_protocol(self, protocol: str):
        pass
