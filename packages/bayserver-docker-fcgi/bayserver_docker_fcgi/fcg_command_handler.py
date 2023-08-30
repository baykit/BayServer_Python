from abc import ABCMeta, abstractmethod

from bayserver_core.protocol.command_handler import CommandHandler

class FcgCommandHandler(CommandHandler, metaclass=ABCMeta):

    @abstractmethod
    def handle_begin_request(self, cmd):
        pass

    @abstractmethod
    def handle_end_request(self, cmd):
        pass

    @abstractmethod
    def handle_params(self, cmd):
        pass

    @abstractmethod
    def handle_stderr(self, cmd):
        pass

    @abstractmethod
    def handle_stdin(self, cmd):
        pass

    @abstractmethod
    def handle_stdout(self, cmd):
        pass
