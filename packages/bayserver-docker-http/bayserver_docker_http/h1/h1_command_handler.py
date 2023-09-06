from abc import ABCMeta, abstractmethod

from bayserver_core.protocol.command_handler import CommandHandler

class H1CommandHandler(CommandHandler, metaclass=ABCMeta):

    @abstractmethod
    def handle_header(self, cmd):
        pass

    @abstractmethod
    def handle_content(self, cmd):
        pass

    @abstractmethod
    def req_finished(self):
        pass

