from abc import ABCMeta, abstractmethod

class Postman(metaclass=ABCMeta):

    @abstractmethod
    def post(self, buf, adr, tag, lis):
        pass

    @abstractmethod
    def flush(self):
        pass

    @abstractmethod
    def post_end(self):
        pass

    @abstractmethod
    def is_zombie(self):
        pass

    @abstractmethod
    def abort(self):
        pass

    @abstractmethod
    def open_valve(self):
        pass