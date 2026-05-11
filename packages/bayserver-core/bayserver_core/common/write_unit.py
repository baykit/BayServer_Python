from typing import Optional

from bayserver_core.rudder.rudder import Rudder
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.internet_address import InternetAddress


class WriteUnit:
    buf: Optional[bytearray]
    file: Optional[Rudder]
    adr: Optional[InternetAddress]
    tag: object
    listener: Optional[DataConsumeListener]
    written: int
    offset: int
    length: int

    def __init__(self,
                 buf: Optional[bytearray] = None,
                 adr: Optional[InternetAddress] = None,
                 tag: object = None,
                 listener: Optional[DataConsumeListener] = None,
                 file: Optional[Rudder] = None,
                 offset: int = 0,
                 length: int = 0):
        self.buf = buf
        self.file = file
        self.adr = adr
        self.tag = tag
        self.listener = listener
        self.written = 0
        self.offset = offset
        self.length = length

    @classmethod
    def for_file(cls, file: Rudder, offset: int, length: int, listener: Optional[DataConsumeListener]) -> "WriteUnit":
        return cls(buf=None, adr=None, tag=None, listener=listener,
                   file=file, offset=offset, length=length)

    def done(self) -> None:
        if self.listener is not None:
            self.listener()

    def skip_formalities(self) -> bool:
        return self.file is not None

    def position(self) -> int:
        if self.skip_formalities():
            return self.offset + self.written
        # Buffer mode in Python: callers slice `buf` as bytes are consumed,
        # so the unread head is always at position 0.
        return 0

    def remaining(self) -> int:
        if self.skip_formalities():
            return self.length - self.written
        return len(self.buf) if self.buf is not None else 0

    def forward(self, length: int) -> None:
        self.written += length

    def has_remaining(self) -> bool:
        if self.skip_formalities():
            return self.length > self.written
        return self.buf is not None and len(self.buf) > 0
