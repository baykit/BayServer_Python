from abc import abstractmethod, ABCMeta
from bayserver_core.docker.docker import Docker

class Secure(Docker, metaclass=ABCMeta):

    @abstractmethod
    def set_app_protocols(self, protocols):
        pass

    @abstractmethod
    def reload_cert(self):
        pass

    @abstractmethod
    def create_transporter(self, bufsize):
        pass

