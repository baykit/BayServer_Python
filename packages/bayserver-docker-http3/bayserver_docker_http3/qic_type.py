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

    PACKET_TYPE_MASK = 0x30
    PACKET_LONG_HEADER = 0x80
    PACKET_TYPE_INITIAL = 0x00
    PACKET_TYPE_ZERO_RTT = 0x10
    PACKET_TYPE_HANDSHAKE = 0x20
    PACKET_TYPE_RETRY = 0x30

    @classmethod
    def packet_type_name(cls, first_byte: int):
        first_byte = (first_byte & cls.PACKET_TYPE_MASK)
        if first_byte & cls.PACKET_LONG_HEADER == 0:
            return "Short"
        elif first_byte == cls.PACKET_TYPE_INITIAL:
            return "Initial"
        elif first_byte == cls.PACKET_TYPE_ZERO_RTT:
            return "ZeroRTT"
        elif first_byte == cls.PACKET_TYPE_HANDSHAKE:
            return "Handshake"
        elif first_byte == cls.PACKET_TYPE_RETRY:
            return "Retry"
        else:
            return "Unkonwn"

