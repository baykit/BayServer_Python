import os
from bayserver_core.rudder.rudder import Rudder


class FdRudder(Rudder):

    fd: int

    def __init__(self, fd: int):
        self.fd = fd

    def __str__(self):
        return f"FileRudder:{self.fd}"

    def key(self) -> object:
        return self.fd

    def set_non_blocking(self) -> None:
        pass

    def read(self, size: int) -> bytes:
        return os.read(self.fd, size)

    def write(self, data: bytes) -> int:
        return os.write(self.fd, data)

    def close(self) -> None:
        return os.close(self.fd)

    def closed(self) -> bool:
        try:
            os.fstat(self.fd)
            return False
        except OSError:
            return True
