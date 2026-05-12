from abc import ABCMeta, abstractmethod

from bayserver_docker_http3.qic_command_handler import QicCommandHandler


class QicHandler(QicCommandHandler, metaclass=ABCMeta):

    @abstractmethod
    def on_protocol_error(self, err):
        """Send protocol error to client. Returns True if the connection
        should be closed."""
        pass
