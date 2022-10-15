from abc import ABCMeta, abstractmethod

class ChannelListener(metaclass=ABCMeta):
    @abstractmethod
    def on_readable(chk_ch):
        pass

    @abstractmethod
    def on_writable(chk_ch):
        pass

    @abstractmethod
    def on_connectable(chk_ch):
        pass

    @abstractmethod
    def on_error(chk_ch, e):
        pass

    @abstractmethod
    def on_closed(chk_ch):
        pass

    @abstractmethod
    def check_timeout(chk_ch, duration_sec):
        pass