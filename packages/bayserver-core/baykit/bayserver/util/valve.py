from abc import ABCMeta, abstractmethod

class Valve(metaclass=ABCMeta):

    @abstractmethod
    def open_valve(self):
        pass
