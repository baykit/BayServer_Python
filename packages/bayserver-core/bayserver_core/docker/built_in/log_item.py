from abc import ABCMeta, abstractmethod

class LogItem(metaclass=ABCMeta):
    def init(self, param):
        pass

    @abstractmethod
    def get_item(self, tour):
        pass
