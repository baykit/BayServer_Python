from abc import ABCMeta, abstractmethod

from bayserver_core.util.reusable import Reusable
from bayserver_core.util.class_util import ClassUtil

class ProtocolHandler(Reusable, metaclass=ABCMeta):


    def __init__(self):
        self.packet_unpacker = None
        self.packet_packer = None
        self.command_unpacker = None
        self.command_packer = None
        self.packet_store = None
        self.server_mode = None
        self.ship = None

    def __str__(self):
        return ClassUtil.get_local_name(type(self)) + f" ship={self.ship}"

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
    # Implements Reusable
    ##################################################
    def reset(self):
        self.command_unpacker.reset()
        self.command_packer.reset()
        self.packet_unpacker.reset()
        self.packet_packer.reset()


    ##################################################
    # Other methods
    ##################################################
    def bytes_received(self, buf):
        return self.packet_unpacker.bytes_received(buf)
