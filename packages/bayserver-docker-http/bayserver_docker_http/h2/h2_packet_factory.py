from bayserver_core.protocol.packet_factory import PacketFactory
from bayserver_docker_http.h2.h2_packet import H2Packet

class H2PacketFactory(PacketFactory):


    def create_packet(self, typ):
        return H2Packet(typ)
