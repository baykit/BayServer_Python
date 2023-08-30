from abc import ABCMeta, abstractmethod;

class ObjectFactory(metaclass=ABCMeta):

    @abstractmethod
    def create_object(self):
        pass