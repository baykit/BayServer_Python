from bayserver_core.protocol.packet import Packet


class H1Packet(Packet):
    MAX_HEADER_LEN = 0  # H1 packet does not have packet header
    MAX_DATA_LEN = 65536

    # space
    SP = " "
    # Line separator */
    CRLF = "\r\n"

    def __init__(self, typ):
        Packet.__init__(self, typ, H1Packet.MAX_HEADER_LEN, H1Packet.MAX_DATA_LEN)

    def __str__(self):
        return f"H1Packet(type={self.type} len={self.data_len()})"
