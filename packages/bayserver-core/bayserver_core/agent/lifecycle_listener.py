from abc import ABCMeta, abstractmethod

class LifecycleListener(metaclass=ABCMeta):
    @abstractmethod
    def add(self, agt_id: int):
        pass

    @abstractmethod
    def remove(self, agt_id: int):
        pass