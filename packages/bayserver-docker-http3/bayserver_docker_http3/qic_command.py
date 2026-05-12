from abc import ABCMeta

from bayserver_core.protocol.command import Command


class QicCommand(Command, metaclass=ABCMeta):
    def __init__(self, typ):
        super().__init__(typ)

    def unpack(self, packet):
        pass

    def pack(self, packet):
        pass

    def handle(self, handler):
        pass
