from abc import ABCMeta, abstractmethod


class Rudder(metaclass=ABCMeta):

    # RudderState (owned by the multiplexer this rudder is registered with).
    # Stored directly on the rudder to avoid dict lookups on every event.
    # Port of Java ChannelRudder.state (6ab73e7).
    state: "object" = None

    # SpiderMultiplexer deferred-registration fields.
    # Port of Java ChannelRudder.pendingOps / inDirtyList (d8677f2).
    pending_ops: int = 0
    in_dirty_list: bool = False
    # Python-side addition: preserve the "connect" flag across _add_operation /
    # _register_channel_ops, which used to live on ChannelOperation.
    pending_to_connect: bool = False

    @abstractmethod
    def key(self) -> object:
        pass

    @abstractmethod
    def set_non_blocking(self) -> None:
        pass

    @abstractmethod
    def read(self, size: int) -> bytes:
        pass


    @abstractmethod
    def write(self, buf: bytes) -> int:
        pass


    @abstractmethod
    def close(self) -> None:
        pass


    @abstractmethod
    def closed(self) -> bool:
        pass

    # Underlying integer file descriptor, or -1 if not file-descriptor backed.
    # Subclasses that wrap a real fd (sockets, regular files) override.
    # Required for the os.sendfile / Direct Boarding path in SpiderMultiplexer.
    def fileno(self) -> int:
        return -1