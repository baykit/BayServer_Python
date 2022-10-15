from abc import ABCMeta, abstractmethod


# interface
class WarpHandler(metaclass=ABCMeta):

    @abstractmethod
    def next_warp_id(self):
        pass

    @abstractmethod
    def new_warp_data(self, warp_id):
        pass

    @abstractmethod
    def post_warp_headers(self, tur):
        pass

    @abstractmethod
    def post_warp_contents(self, tur, buf, start, length, callback):
        pass

    @abstractmethod
    def post_warp_end(self, tur):
        pass

    #
    # Verify if protocol is allowed
    #
    @abstractmethod
    def verify_protocol(self, protocol):
        pass
