from abc import ABCMeta, abstractmethod

from bayserver_core.protocol.command_handler import CommandHandler

class H2CommandHandler(CommandHandler, metaclass=ABCMeta):

    @abstractmethod
    def handle_preface(self, cmd):
        pass

    @abstractmethod
    def handle_headers(self, cmd):
        pass

    @abstractmethod
    def handle_data(self, cmd):
        pass

    @abstractmethod
    def handle_priority(self, cmd):
        pass

    @abstractmethod
    def handle_settings(self, cmd):
        pass

    @abstractmethod
    def handle_window_update(self, cmd):
        pass

    @abstractmethod
    def handle_go_away(self, cmd):
        pass

    @abstractmethod
    def handle_ping(self, cmd):
        pass

    @abstractmethod
    def handle_rst_stream(self, cmd):
        pass

    def __init__(self, pkt_store):
        super().__init__(pkt_store)
