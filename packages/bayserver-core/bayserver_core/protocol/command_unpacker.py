from abc import ABCMeta, abstractmethod
from typing import Any

from bayserver_core.protocol.packet import Packet
from bayserver_core.util.reusable import Reusable

class CommandUnPacker(Reusable, metaclass=ABCMeta):
    def packet_received(self, pkt: Packet, adr: Any):
        pass