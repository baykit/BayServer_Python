from abc import abstractmethod

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_docker_http.h2.h2_command_handler import H2CommandHandler


class H2Handler(H2CommandHandler):

    # Send protocol error to client
    @abstractmethod
    def on_protocol_error(self, e: ProtocolException) -> bool:
        pass