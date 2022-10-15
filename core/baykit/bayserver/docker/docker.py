from abc import ABCMeta, abstractmethod

class Docker(metaclass=ABCMeta):

    @abstractmethod
    def init(ini, parent):
        pass