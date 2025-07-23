from aioquic.asyncio import QuicConnectionProtocol
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import QuicEvent

from bayserver_core.bay_log import BayLog
from bayserver_docker_http3 import h3port_docker as h3
from bayserver_docker_http3.qic_ticket import QicTicket


class QuicConnectionProtocolEx(QuicConnectionProtocol):
    ticket: QicTicket

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ticket = QicTicket(self, h3.h3_docker)

    def quic_event_received(self, event: QuicEvent) -> None:
        if self.ticket.get_sender() is None and len(self._quic._network_paths) > 0:
            self.ticket.set_sender(self._quic._network_paths[0].addr)
        self.ticket.notify_quic_event(event)

    def get_connection(self) -> QuicConnection:
        return self._quic

    def connection_made(self, transport):
        super().connection_made(transport)
        sock = transport.get_extra_info("socket")
        addr = sock.getsockname()
        BayLog.info(f"QUIC server listening on {addr}")