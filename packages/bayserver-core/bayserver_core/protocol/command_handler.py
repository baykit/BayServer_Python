from abc import ABCMeta, abstractmethod
from bayserver_core.util.reusable import Reusable

class CommandHandler(Reusable, metaclass=ABCMeta):
    pass