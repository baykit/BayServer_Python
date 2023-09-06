from abc import ABCMeta, abstractmethod

class ReqContentHandler(metaclass=ABCMeta):
    #
    # interface
    #
    @abstractmethod
    def on_read_content(self, tur, buf, start, len):
        pass

    @abstractmethod
    def on_end_content(self, tur):
        pass

    @abstractmethod
    def on_abort(self, tur):
        return False

    dev_null = None


#
# private
#
class _DevNullReqContentHandler(ReqContentHandler):
    def on_read_content(self, tur, buf, start, len):
        pass

    def on_end_content(self, tur):
        pass

    def on_abort(self, tur):
        return False


ReqContentHandler.dev_null = _DevNullReqContentHandler()
