from bayserver_core.protocol.packet_factory import PacketFactory

from bayserver_docker_fcgi.fcg_packet import FcgPacket

class FcgPacketFactory(PacketFactory):

    def create_packet(self, type):
        return FcgPacket(type)