from abc import abstractmethod, ABCMeta
from bayserver_core.docker.docker import Docker

class Club(Docker, metaclass=ABCMeta):

    # Get the file name part of club
    @abstractmethod
    def file_name(self) -> str:
        pass

    # Get the ext (file extension part) of club
    @abstractmethod
    def extension(self) -> str:
        pass

    # Check if file name matches this club
    @abstractmethod
    def matches(self, fname) -> bool:
        pass

    # Get charset of club
    @abstractmethod
    def charset(self) -> str:
        pass

    # Check if this club decodes PATH_INFO
    @abstractmethod
    def decode_path_info(self) -> bool:
        pass

    # Arrive
    @abstractmethod
    def arrive(self, tur) -> None:
        pass
