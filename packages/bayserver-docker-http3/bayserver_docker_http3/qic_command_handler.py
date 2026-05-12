from abc import ABCMeta, abstractmethod

from bayserver_core.protocol.command_handler import CommandHandler


class QicCommandHandler(CommandHandler, metaclass=ABCMeta):

    @abstractmethod
    def handle_headers(self, cmd):
        pass

    @abstractmethod
    def handle_data(self, cmd):
        pass

    @abstractmethod
    def handle_finished(self, cmd):
        pass
