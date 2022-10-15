from baykit.bayserver.protocol.packet_factory import PacketFactory
from baykit.bayserver.docker.http.h1.h1_packet import H1Packet


class H1PacketFactory(PacketFactory):

    def create_packet(self, typ):
        return H1Packet(typ)