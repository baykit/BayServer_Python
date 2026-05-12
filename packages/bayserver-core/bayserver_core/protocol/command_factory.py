from abc import ABCMeta, abstractmethod


class CommandFactory(metaclass=ABCMeta):
    """Per-protocol factory that creates Command instances by type.

    Used by CommandStore to populate per-type Command pools without the
    pool itself needing to know the concrete Command classes.
    """

    @abstractmethod
    def create_command(self, type):
        pass
