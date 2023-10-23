from bayserver_core.protocol.packet import Packet

from bayserver_docker_http3.qic_type import QicType

class QicPacket(Packet):

    MAX_DATAGRAM_SIZE = 1350

    def __init__(self):
        super().__init__(QicType.SHORT, 0, QicPacket.MAX_DATAGRAM_SIZE)

    def __str__(self):
        return f"QicPacket[len={len(self.buf)}]"
