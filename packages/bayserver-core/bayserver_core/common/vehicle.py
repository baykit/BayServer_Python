from abc import ABCMeta, abstractmethod


class Vehicle(metaclass=ABCMeta):

    id: int

    #
    # abstract method
    #
    @abstractmethod
    def run(self) -> None:
        pass

    @abstractmethod
    def on_timer(self) -> None:
        pass

    def __init__(self, id: int) -> None:
        self.id = id