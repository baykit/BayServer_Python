from abc import ABCMeta, abstractmethod

from bayserver_core.bcf.bcf_element import BcfElement


class Docker(metaclass=ABCMeta):

    @abstractmethod
    def init(self, ini: BcfElement, parent: "Docker") -> bool:
        pass