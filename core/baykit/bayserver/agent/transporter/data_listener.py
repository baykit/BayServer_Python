from abc import ABCMeta, abstractmethod

class DataListener(metaclass=ABCMeta):
    @abstractmethod
    def notify_connect(self):
        pass

    @abstractmethod
    def notify_read(self, buf, adr):
        pass

    @abstractmethod
    def notify_eof(self):
        pass

    @abstractmethod
    def notify_handshake_done(self, proto):
        pass

    @abstractmethod
    def notify_protocol_error(self, e):
        pass

    @abstractmethod
    def notify_close(self):
        pass

    @abstractmethod
    def check_timeout(self, duration_sec):
        pass

