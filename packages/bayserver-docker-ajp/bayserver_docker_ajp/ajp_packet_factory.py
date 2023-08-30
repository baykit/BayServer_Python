from bayserver_core.protocol.packet_factory import PacketFactory
from bayserver_docker_ajp.ajp_packet import AjpPacket


class AjpPacketFactory(PacketFactory):

    def create_packet(self, typ):
        return AjpPacket(typ)
