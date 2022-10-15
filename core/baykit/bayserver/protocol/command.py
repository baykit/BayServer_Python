from abc import ABCMeta, abstractmethod


class Command(metaclass=ABCMeta):

    @abstractmethod
    def unpack(self, pkt):
        pass

    @abstractmethod
    def pack(self, pkt):
        pass

    @abstractmethod
    def handle(self, handler):
        pass

    def __init__(self, type):
        self.type = type