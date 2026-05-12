from bayserver_core.protocol.packet import Packet


class QicCommandPacket(Packet):
    """Dummy packet; H3 commands are dispatched directly from H3 events
    rather than from a wire-level packet, so this class only exists to
    satisfy the Command base class' generic type parameter."""

    def __init__(self, typ):
        super().__init__(typ, 0, 0)

    def __str__(self):
        return f"QicCmd packet[type={self.type}]"
