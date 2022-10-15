from abc import ABCMeta, abstractmethod

class PacketFactory(metaclass=ABCMeta):

    @abstractmethod
    def create_packet(self, type):
       pass
