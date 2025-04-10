from abc import ABCMeta, abstractmethod

class Rudder(metaclass=ABCMeta):

    @abstractmethod
    def key(self) -> object:
        pass

    @abstractmethod
    def set_non_blocking(self) -> None:
        pass

    @abstractmethod
    def read(self, size: int) -> bytes:
        pass


    @abstractmethod
    def write(self, buf: bytes) -> int:
        pass


    @abstractmethod
    def close(self) -> None:
        pass


    @abstractmethod
    def closed(self) -> bool:
        pass