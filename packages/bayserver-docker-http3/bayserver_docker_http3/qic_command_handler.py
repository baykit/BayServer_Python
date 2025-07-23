from abc import ABCMeta

from bayserver_core.protocol.command_handler import CommandHandler


class QicCommandHandler(CommandHandler, metaclass=ABCMeta):

    pass
