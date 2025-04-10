from typing import BinaryIO

from bayserver_core.rudder.rudder import Rudder


class BinaryIORudder(Rudder):
    file: BinaryIO

    def __init__(self, f: BinaryIO):
        if not isinstance(f, BinaryIO):
            raise TypeError(f"Invalid type: {f}")
        self.file = f

    def __str__(self):
        return f"BinIoRd:{self.file}"

    def key(self) -> object:
        return self.file

    def set_non_blocking(self) -> None:
        pass

    def read(self, size: int) -> bytes:
        return self.file.read(size)

    def write(self, data: bytes) -> int:
        return self.file.write(data)

    def close(self) -> None:
        self.file.close()