class QicType:
    # quiche packet type codes (croute exposes the same integers via
    # PacketHeader.type)
    INITIAL = 1
    RETRY = 2
    HANDSHAKE = 3
    ZERO_RTT = 4
    SHORT = 5
    VERSION_NEGOTIATION = 6
