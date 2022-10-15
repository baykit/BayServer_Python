from abc import ABCMeta, abstractmethod

class LogItemFactory(metaclass=ABCMeta):

    @abstractmethod
    def new_log_item(self):
        pass
