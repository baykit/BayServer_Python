import abc
from abc import abstractmethod


class Recipient(metaclass=abc.ABCMeta):
    #
    #Receives letters.
    #
    @abstractmethod
    def receive(self, wait: bool) -> bool:
        pass

    @abstractmethod
    def wakeup(self):
        pass