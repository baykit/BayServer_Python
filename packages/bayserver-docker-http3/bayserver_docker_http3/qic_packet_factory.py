from bayserver_core.protocol.packet_factory import PacketFactory
from bayserver_docker_http3.qic_packet import QicPacket

class QicPacketFactory(PacketFactory):

    def create_packet(self, typ):
        return QicPacket(typ)