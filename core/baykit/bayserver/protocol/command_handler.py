from abc import ABCMeta, abstractmethod
from baykit.bayserver.util.reusable import Reusable

class CommandHandler(Reusable, metaclass=ABCMeta):
    pass