from abc import ABCMeta, abstractmethod


class ProtocolHandlerFactory(metaclass=ABCMeta):

    def create_protocol_handler(self, pkt_store, cmd_store=None):
        # cmd_store is the per-agent Command pool (CommandStore). Optional
        # so factories that haven't been migrated yet keep working; once
        # a factory registers a CommandFactory with CommandStore the
        # corresponding pool will be wired through.
        pass
