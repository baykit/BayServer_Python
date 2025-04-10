from io import IOBase

from bayserver_core.rudder.rudder import Rudder


class IORudder(Rudder):
    file: IOBase

    def __init__(self, f: IOBase):
        if not isinstance(f, IOBase):
            raise TypeError(f"Invalid type: {f}")
        self.file = f

    def __str__(self):
        return f"IoRd:{self.file}"

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

    def closed(self) -> bool:
        return self.file.closed