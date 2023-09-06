from typing import Dict, Optional
import os

from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket


from bayserver_core.bay_message import BayMessage
from bayserver_core.config_exception import ConfigException
from bayserver_core.docker.base.port_base import PortBase
from bayserver_docker_http3.h3_docker import H3Docker
from bayserver_docker_http3.udp_inbound_data_listener import UdpInboundDataListener
from bayserver_docker_http3.udp_transporter import UdpTransporter
from bayserver_core.symbol import Symbol


class H3PortDocker(PortBase, H3Docker):

    class SessionTicketStore:
        """
        Simple in-memory store for session tickets.
        """

        def __init__(self) -> None:
            self.tickets: Dict[bytes, SessionTicket] = {}

        def add(self, ticket: SessionTicket) -> None:
            self.tickets[ticket.ticket] = ticket

        def pop(self, label: bytes) -> Optional[SessionTicket]:
            return self.tickets.pop(label, None)


    def __init__(self):
        PortBase.__init__(self)
        self.config = None
        self.create_protocol = None
        self.session_ticket_fetcher = None
        self.session_ticket_handler = None
        self.retry = True
        self.quic_log_dir = "log"
        self.secrets_log_file = "log/quic_secrets.log"

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        # create QUIC logger
        if self.quic_log_dir:
            if not os.path.exists(self.quic_log_dir):
                os.mkdir(self.quic_log_dir)
            quic_logger = QuicFileLogger(self.quic_log_dir)
        else:
            quic_logger = None

        # open SSL log file
        if self.secrets_log_file:
            secrets_log = open(self.secrets_log_file, "a")
        else:
            secrets_log = None

        self.config = QuicConfiguration(
            alpn_protocols = H3_ALPN,
            is_client = False,
            max_datagram_frame_size = 65536,
            quic_logger = quic_logger,
            secrets_log_file = secrets_log,
        )

        if not self.secure_docker.cert_file:
            raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_SSL_CERT_FILE_NOT_SPECIFIED))
        if not self.secure_docker.key_file:
            raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_SSL_KEY_FILE_NOT_SPECIFIED));

        self.config.load_cert_chain(self.secure_docker.cert_file, self.secure_docker.key_file)

        ticket_store = H3PortDocker.SessionTicketStore()
        self.session_ticket_fetcher = ticket_store.pop
        self.session_ticket_handler = ticket_store.add
        #self.create_protocol = HttpServerProtocol

    ######################################################
    # Implements Port
    ######################################################

    def protocol(self):
        return H3Docker.PROTO_NAME


    ######################################################
    # Implements PortBase
    ######################################################
    def support_anchored(self):
        return False

    def support_unanchored(self):
        return True

    def new_transporter(self, agt, skt):
        lis = UdpInboundDataListener()
        tp = UdpTransporter(True, 2048)
        lis.init_udp(skt, agt, tp, self)
        tp.init(agt.non_blocking_handler, skt, lis)
        return tp

    ######################################################
    # Class initializer
    ######################################################
