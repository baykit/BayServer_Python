from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.internet_address import InternetAddress

class WriteUnit:
    buf: bytearray
    adr: str
    tag: object
    listener: DataConsumeListener

    def __init__(self, buf: bytearray, adr: InternetAddress, tag: object, listener: DataConsumeListener):
        self.buf = buf
        self.adr = adr
        self.tag = tag
        self.listener = listener

    def done(self):
        if self.listener is not None:
            self.listener()