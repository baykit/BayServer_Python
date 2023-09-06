from abc import ABCMeta, abstractmethod

from bayserver_core.util.reusable import Reusable

class PacketUnPacker(Reusable, metaclass=ABCMeta):

    @abstractmethod
    def bytes_received(self, bytes):
        pass
