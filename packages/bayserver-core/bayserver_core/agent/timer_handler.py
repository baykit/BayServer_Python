from abc import ABCMeta, abstractmethod

class TimerHandler(metaclass=ABCMeta):
    @abstractmethod
    def on_timer(self):
        pass