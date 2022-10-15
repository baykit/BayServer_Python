from abc import ABCMeta, abstractmethod

from baykit.bayserver.util.reusable import Reusable

class CommandUnPacker(Reusable, metaclass=ABCMeta):
    def packet_received(self, pkt):
        pass