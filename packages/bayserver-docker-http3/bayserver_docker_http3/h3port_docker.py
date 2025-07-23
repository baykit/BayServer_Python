import asyncio
import os
import threading
from typing import Dict, Optional

from aioquic.asyncio import serve
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.bayserver import BayServer
from bayserver_core.config_exception import ConfigException
from bayserver_core.docker.base.port_base import PortBase
from bayserver_core.sink import Sink
from bayserver_core.symbol import Symbol
from bayserver_docker_http3.h3_docker import H3Docker
from bayserver_docker_http3.quic_connection_protocol_ex import QuicConnectionProtocolEx

h3_docker = None

try:
    import uvloop
except ImportError:
    uvloop = None


def start_h3_server(h3Port: "H3PortDocker") -> None:
    loop = asyncio.new_event_loop()
    store = h3Port.SessionTicketStore()
    try:
        BayLog.info("Starting H3 server port=%d", h3Port.port())
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            serve(
                "::",
                h3Port.port(),
                configuration=h3Port.config,
                create_protocol=QuicConnectionProtocolEx,
                session_ticket_fetcher=store.pop,
                session_ticket_handler=store.add,
                retry=True,
            )
        )
        loop.run_forever()  # 必要に応じて永続化（例：serve()が持続しない場合）
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

class H3PortDocker(PortBase, H3Docker):

    config: QuicConfiguration
    session_ticket_fetcher: SessionTicket
    session_ticket_handler: SessionTicket
    retry: bool
    quic_log_dir: str
    secrets_log_file: str

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

        global h3_docker
        h3_docker = self

        self.quic_log_dir = "log"
        self.secrets_log_file = "log/quic_secrets.log"

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

        if not self._secure_docker.cert_file:
            raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_SSL_CERT_FILE_NOT_SPECIFIED))
        if not self._secure_docker.key_file:
            raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_SSL_KEY_FILE_NOT_SPECIFIED));

        self.config.load_cert_chain(self._secure_docker.cert_file, self._secure_docker.key_file)

        if BayServer.is_child():
            thread = threading.Thread(target=start_h3_server, args=(self,))
            thread.start()

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "quic_log_dir":
            self.quic_log_dir = kv.value

        elif key == "secrets_log_file":
            self.secrets_log_file = kv.value

        else:
            return super().init_key_val(kv)
        return True

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
        raise Sink()

    ######################################################
    # Class initializer
    ######################################################
