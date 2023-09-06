from abc import ABCMeta, abstractmethod


class InboundHandler(metaclass=ABCMeta):

    #
    #  Send protocol error
    #   return true if connection must be closed
    #
    @abstractmethod
    def send_req_protocol_error(self, protocol_ex):
        pass

    #
    #  Send HTTP headers to client
    #
    @abstractmethod
    def send_res_headers(self, tur):
        pass

    #
    # Send Contents to client
    #
    @abstractmethod
    def send_res_content(self, tur, bytes, ofs, len, callback):
        pass

    #
    # Send end of contents to client.
    #  sendEnd cannot refer Tour instance because it is discarded before call.
    #
    @abstractmethod
    def send_end_tour(self, tur, keep_alive, callback):
        pass
