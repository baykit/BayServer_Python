from abc import ABCMeta, abstractmethod

class Reusable(metaclass=ABCMeta):

    @abstractmethod
    def reset(self):
        pass
