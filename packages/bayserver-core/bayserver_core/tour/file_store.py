import collections
import os
import threading
import time
from typing import Optional

from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog
from bayserver_core.rudder.io_rudder import IORudder
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.util.directory_exception import DirectoryException


class FileStore:
    """Java tour/FileStore port. Caches a small pool of open file Rudders for the
    Direct Boarding (sendfile) path, evicting LRU on overflow. Files larger than
    `max_cargo_size` are still tracked but stored without a Rudder."""

    class FileInfo:
        file_name: str
        rudder: Optional[Rudder]
        file_length: int

        def __init__(self, file_name: str, rd: Optional[Rudder], file_length: int):
            self.file_name = file_name
            self.rudder = rd
            self.file_length = file_length
            self._last_access_time = time.time()

        def access(self):
            self._last_access_time = time.time()

        def expired(self, lifespan_sec: int) -> bool:
            return time.time() - self._last_access_time > lifespan_sec

        def close(self):
            if self.rudder is not None:
                try:
                    self.rudder.close()
                except IOError as e:
                    BayLog.error_e(e, [])
                self.rudder = None

    _instance: Optional["FileStore"] = None
    _instance_lock = threading.Lock()

    def __init__(self, lifespan_sec: int, max_cargos: int, max_cargo_size_bytes: int):
        self._lifespan_sec = lifespan_sec
        self._max_cargos = max_cargos
        self._max_cargo_size_bytes = max_cargo_size_bytes
        self._files: "collections.OrderedDict[str, FileStore.FileInfo]" = collections.OrderedDict()
        self._lock = threading.Lock()

    def get(self, path: str) -> "FileStore.FileInfo":
        with self._lock:
            info = self._files.get(path)
            if info is not None and info.expired(self._lifespan_sec):
                info.close()
                del self._files[path]
                info = None

            if info is None:
                if os.path.isdir(path):
                    raise DirectoryException()

                size = os.path.getsize(path)
                if size > self._max_cargo_size_bytes:
                    info = FileStore.FileInfo(path, None, size)
                else:
                    f = open(path, "rb", buffering=False)
                    info = FileStore.FileInfo(path, IORudder(f), size)

                self._files[path] = info
                self._evict_lru()
            else:
                # LRU touch
                self._files.move_to_end(path)

            info.access()
            return info

    def _evict_lru(self):
        while len(self._files) > self._max_cargos:
            _, evicted = self._files.popitem(last=False)
            evicted.close()

    @classmethod
    def get_file_store(cls) -> "FileStore":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = FileStore(
                    bs.BayServer.harbor.cargo_lifespan_sec(),
                    bs.BayServer.harbor.max_direct_boardings(),
                    bs.BayServer.harbor.max_cargo_size())
            return cls._instance
