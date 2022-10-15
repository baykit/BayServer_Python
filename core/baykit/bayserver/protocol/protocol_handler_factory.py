from abc import ABCMeta, abstractmethod

class ProtocolHandlerFactory(metaclass=ABCMeta):

    def create_protocol_handler(self, pkt_store):
        pass
