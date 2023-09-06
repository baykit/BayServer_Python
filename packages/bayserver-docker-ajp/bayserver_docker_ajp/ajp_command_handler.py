from abc import ABCMeta, abstractmethod

from bayserver_core.protocol.command_handler import CommandHandler

class AjpCommandHandler(CommandHandler, metaclass=ABCMeta):
    @abstractmethod
    def handle_forward_request(self, cmd):
        pass

    @abstractmethod
    def handle_data(self, cmd):
        pass

    @abstractmethod
    def handle_send_body_chunk(self, cmd):
        pass

    @abstractmethod
    def handle_send_headers(self, cmd):
        pass

    @abstractmethod
    def handle_shutdown(self, cmd):
        pass

    @abstractmethod
    def handle_end_response(self, cmd):
        pass

    @abstractmethod
    def handle_get_body_chunk(self, cmd):
        pass

    @abstractmethod
    def need_data(self):
        pass
