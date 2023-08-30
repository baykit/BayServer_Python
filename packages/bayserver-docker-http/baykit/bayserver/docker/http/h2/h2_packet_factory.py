from baykit.bayserver.protocol.packet_factory import PacketFactory
from baykit.bayserver.docker.http.h2.h2_packet import H2Packet

class H2PacketFactory(PacketFactory):


    def create_packet(self, typ):
        return H2Packet(typ)
