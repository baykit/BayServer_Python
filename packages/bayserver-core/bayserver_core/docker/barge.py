from abc import ABCMeta, abstractmethod
from typing import Tuple

from bayserver_core.docker.docker import Docker
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.tour.tour import Tour
from bayserver_core.util.headers import Headers


# "Barge" is a metaphor for the cache management function.
class Barge(Docker, metaclass=ABCMeta):

    # "Cargo" is a metaphor for cached data.
    class Cargo(metaclass=ABCMeta):

        @abstractmethod
        def path(self) -> str:
            pass

        @abstractmethod
        def headers(self) -> Headers:
            pass

        @abstractmethod
        def content(self) -> bytes:
            pass

        @abstractmethod
        def length(self) -> int:
            pass

        @abstractmethod
        def on_barge(self) -> bool:
            pass

        @abstractmethod
        def exceeded(self) -> bool:
            pass

        @abstractmethod
        def save_headers(self, headers: Headers) -> None:
            pass

        @abstractmethod
        def save_content(self, data: bytes, offset: int, length: int) -> None:
            pass

        @abstractmethod
        def end_save(self) -> None:
            pass

        @abstractmethod
        def release_rudder(self, rudder: Rudder) -> None:
            pass

    # Barge name (path)
    @abstractmethod
    def name(self) -> str:
        pass

    # Capacity of the barge. (in mega-bytes)
    @abstractmethod
    def capacity(self) -> int:
        pass

    # Get cargo on the barge.
    @abstractmethod
    def get_cargo(self, tour: Tour) -> Tuple["Barge.Cargo", Rudder]:
        pass
