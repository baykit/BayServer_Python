from abc import abstractmethod

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_docker_http3.qic_command_handler import QicCommandHandler


class QicHandler(QicCommandHandler):
    # Send protocol error to client
    @abstractmethod
    def on_protocol_error(self, e: ProtocolException) -> bool:
        pass