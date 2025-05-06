import abc
from abc import abstractmethod


class Postpone(metaclass=abc.ABCMeta):

    @abstractmethod
    def run(self) -> None:
        pass