from abc import ABCMeta, abstractmethod

class DataConsumeListener(metaclass=ABCMeta):

    @abstractmethod
    def done(self):
        pass
