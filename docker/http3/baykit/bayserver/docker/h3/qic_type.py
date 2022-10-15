from aioquic.quic import packet

#
# Quic packet type
#

class QicType:
    INITIAL = 0,
    RETRY = 1,
    HANDSHAKE = 2,
    ZERO_RTT = 3,
    SHORT = 4,
    VERSION_NEGOTIATION = 5


    @classmethod
    def packet_type_name(cls, type):
        type = type & packet.PACKET_TYPE_MASK
        if type & packet.PACKET_LONG_HEADER == 0:
            return "Short"
        elif type == packet.PACKET_TYPE_INITIAL:
            return "Initial"
        elif type == packet.PACKET_TYPE_ZERO_RTT:
            return "ZeroRTT"
        elif type == packet.PACKET_TYPE_HANDSHAKE:
            return "Handshake"
        elif type == packet.PACKET_TYPE_RETRY:
            return "Retry"
        else:
            return "Unkonwn"

