from abc import ABCMeta, abstractmethod

from bayserver_core.util.reusable import Reusable

class CommandUnPacker(Reusable, metaclass=ABCMeta):
    def packet_received(self, pkt):
        pass