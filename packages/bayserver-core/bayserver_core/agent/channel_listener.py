from abc import ABCMeta, abstractmethod

class ChannelListener(metaclass=ABCMeta):
    @abstractmethod
    def on_readable(self, chk_ch):
        pass

    @abstractmethod
    def on_writable(self, chk_ch):
        pass

    @abstractmethod
    def on_connectable(self, chk_ch):
        pass

    @abstractmethod
    def on_error(self, chk_ch, e):
        pass

    @abstractmethod
    def on_closed(self, chk_ch):
        pass

    @abstractmethod
    def check_timeout(self, chk_ch, duration_sec):
        pass