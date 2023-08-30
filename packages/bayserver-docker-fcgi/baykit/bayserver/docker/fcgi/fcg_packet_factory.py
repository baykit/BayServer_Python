from baykit.bayserver.protocol.packet_factory import PacketFactory

from baykit.bayserver.docker.fcgi.fcg_packet import FcgPacket

class FcgPacketFactory(PacketFactory):

    def create_packet(self, type):
        return FcgPacket(type)