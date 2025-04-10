from abc import ABCMeta, abstractmethod
from typing import Callable

from bayserver_core.protocol.command import Command
from bayserver_core.protocol.command_handler import CommandHandler
from bayserver_core.protocol.command_packer import CommandPacker
from bayserver_core.protocol.command_unpacker import CommandUnPacker
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.packet_unpacker import PacketUnPacker
from bayserver_core.ship.ship import Ship
from bayserver_core.util.class_util import ClassUtil
from bayserver_core.util.reusable import Reusable


class ProtocolHandler(Reusable, metaclass=ABCMeta):

    packet_unpacker: PacketUnPacker
    packet_packer: PacketPacker
    command_unpacker: CommandUnPacker
    command_packer: CommandPacker
    command_handler: CommandHandler
    server_mode: bool
    ship: Ship

    def __init__(self,
                 packet_unpacker: PacketUnPacker,
                 packet_packer: PacketPacker,
                 command_unpacker: CommandUnPacker,
                 command_packer: CommandPacker,
                 command_handler: CommandHandler,
                 server_mode: bool):
        self.packet_unpacker = packet_unpacker
        self.packet_packer = packet_packer
        self.command_unpacker = command_unpacker
        self.command_packer = command_packer
        self.command_handler = command_handler
        self.server_mode = server_mode
        self.ship = None

    def init(self, sip: Ship) -> None:
        self.ship = sip

    def __str__(self):
        return ClassUtil.get_local_name(type(self)) + f" ship={self.ship}"

    ##################################################
    # Implements Reusable
    ##################################################
    def reset(self):
        self.command_unpacker.reset()
        self.command_packer.reset()
        self.packet_unpacker.reset()
        self.packet_packer.reset()
        self.command_handler.reset()
        self.server_mode = False
        self.ship = None


    ##################################################
    # Abstract methods
    ##################################################

    @abstractmethod
    def protocol(self):
        pass

    #
    # Get max of request data size (maybe not packet size)
    #
    @abstractmethod
    def max_req_packet_data_size(self):
        pass

    #
    # Get max of response data size (maybe not packet size)
    #
    @abstractmethod
    def max_res_packet_data_size(self):
        pass




    ##################################################
    # Other methods
    ##################################################
    def bytes_received(self, buf):
        return self.packet_unpacker.bytes_received(buf)

    def post(self, c: Command, lis: Callable[[], None] = None) -> None:
        self.command_packer.post(self.ship, c, lis)
