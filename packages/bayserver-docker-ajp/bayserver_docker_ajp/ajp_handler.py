from abc import abstractmethod
from typing import List

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_docker_ajp.ajp_command_handler import AjpCommandHandler


class AjpHandler(AjpCommandHandler):

    # Send protocol error to client
    @abstractmethod
    def on_protocol_error(self, e:ProtocolException, stk: List[str]) -> bool:
        pass