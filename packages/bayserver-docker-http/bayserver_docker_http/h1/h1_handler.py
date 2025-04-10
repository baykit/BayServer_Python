from abc import abstractmethod

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_docker_http.h1.h1_command_handler import H1CommandHandler


class H1Handler(H1CommandHandler):

    # Send protocol error to client
    @abstractmethod
    def on_protocol_error(self, e: ProtocolException) -> bool:
        pass