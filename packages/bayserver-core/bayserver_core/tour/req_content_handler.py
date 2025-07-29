from abc import ABCMeta, abstractmethod

from bayserver_core.tour.content_consume_listener import ContentConsumeListener


class ReqContentHandler(metaclass=ABCMeta):
    #
    # interface
    #
    @abstractmethod
    def on_read_req_content(self, tur: "Tour", buf: bytearray, start: int, length: int, lis: ContentConsumeListener):
        pass

    @abstractmethod
    def on_end_req_content(self, tur: "Tour"):
        pass

    @abstractmethod
    def on_abort_req(self, tur: "Tour"):
        return False

    dev_null = None


#
# private
#
class _DevNullReqContentHandler(ReqContentHandler):
    def on_read_req_content(self, tur, buf, start, length, lis):
        pass

    def on_end_req_content(self, tur):
        pass

    def on_abort_req(self, tur):
        return False


ReqContentHandler.dev_null = _DevNullReqContentHandler()
