import os
import threading
import time
import traceback
from collections import OrderedDict
from typing import List, Optional, Tuple

from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog
from bayserver_core.docker.barge import Barge
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.rudder.io_rudder import IORudder
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.tour.tour import Tour
from bayserver_core.util.headers import Headers
from bayserver_core.util.simple_buffer import SimpleBuffer
from bayserver_core.util.string_util import StringUtil


class MemBargeDocker(DockerBase, Barge):
    """In-memory cache barge. Caches the response (headers + body) for a
    request URI under a fixed total capacity, evicting LRU on overflow.

    Java MemBargeDocker port; uses os.pipe() in place of Java's NIO Pipe to
    notify waiters when a cargo finishes loading.
    """

    DEFAULT_CAPACITY = 32 * 1024 * 1024  # 32 MB

    class MemCargo(Barge.Cargo):
        LOADING = 1
        LOADED = 2
        EXCEEDED = 3

        def __init__(self, parent: "MemBargeDocker", path: str):
            self._parent = parent
            self._path = path
            self._length = 0
            self._status = MemBargeDocker.MemCargo.LOADING
            self._buf = SimpleBuffer()
            self._headers = Headers()
            self._last_accessed_time = time.time()
            self._waiters: List[Rudder] = []
            self._lock = threading.Lock()

        ######################################################
        # Implements Cargo
        ######################################################

        def path(self) -> str:
            return self._path

        def headers(self) -> Headers:
            return self._headers

        def content(self) -> bytes:
            return bytes(self._buf.byte_data()[:self._buf.__len__()])

        def length(self) -> int:
            return self._buf.__len__()

        def on_barge(self) -> bool:
            return self._status == MemBargeDocker.MemCargo.LOADED

        def exceeded(self) -> bool:
            return self._status == MemBargeDocker.MemCargo.EXCEEDED

        def save_headers(self, headers: Headers) -> None:
            if self.on_barge():
                raise RuntimeError("already saved")
            if self.exceeded():
                return
            headers.copy_to(self._headers)

        def save_content(self, data, offset: int, length: int) -> None:
            if self.on_barge():
                raise RuntimeError("already saved")
            if self.exceeded():
                return

            BayLog.debug("%s save content len=%d", self, length)
            self._length += length

            max_size = bs.BayServer.harbor.max_cargo_size()
            if self._length > max_size:
                BayLog.debug("%s cargo exceeded: len=%d max=%d", self, self._length, max_size)
                self._status = MemBargeDocker.MemCargo.EXCEEDED
                self._buf.reset()
                return

            self._buf.put(data, offset, length)

        def end_save(self) -> None:
            with self._lock:
                if self.on_barge():
                    raise RuntimeError("already saved")
                if self.exceeded():
                    return

                BayLog.debug("%s end save", self)
                self._status = MemBargeDocker.MemCargo.LOADED
                self._parent._add_total(self._length)

                # Notify waiters by writing one byte into each pipe sink.
                for rd in self._waiters:
                    try:
                        BayLog.debug("%s notify waiter", self)
                        rd.write(b"\x00")
                    except IOError as e:
                        BayLog.error_e(e, traceback.format_stack())

        def release_rudder(self, rudder: Rudder) -> None:
            with self._lock:
                if rudder in self._waiters:
                    self._waiters.remove(rudder)

        ######################################################
        # Private methods
        ######################################################

        def _access(self) -> None:
            self._last_accessed_time = time.time()

        def _expired(self) -> bool:
            return (not self._waiters
                    and time.time() - self._last_accessed_time
                    > bs.BayServer.harbor.cargo_lifespan_sec())

        def _add_waiter(self, rd: Rudder) -> None:
            self._waiters.append(rd)

    def __init__(self):
        super().__init__()
        self.name = None
        self.capacity_bytes = MemBargeDocker.DEFAULT_CAPACITY
        self._total_size = 0
        self._cargo_map: "OrderedDict[str, MemBargeDocker.MemCargo]" = OrderedDict()
        self._lock = threading.Lock()

    def __str__(self):
        return f"MemBargeDocker[{self.name}]"

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)
        self.name = elm.arg
        if StringUtil.is_empty(self.name):
            self.name = "*"

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "capacity":
            self.capacity_bytes = StringUtil.parse_size(kv.value)
        else:
            return super().init_key_val(kv)
        return True

    ######################################################
    # Implements Barge
    ######################################################

    def name(self) -> str:
        return self.name

    def capacity(self) -> int:
        return self.capacity_bytes

    def get_cargo(self, tour: Tour) -> Tuple["MemBargeDocker.MemCargo", Optional[Rudder]]:
        with self._lock:
            path = tour.req.uri
            cgo = self._cargo_map.get(path)
            source_rd: Optional[Rudder] = None

            if cgo is not None and not cgo._waiters and cgo._expired():
                self._total_size -= cgo.length()
                del self._cargo_map[path]
                cgo = None

            if cgo is None:
                cgo = MemBargeDocker.MemCargo(self, path)
                self._cargo_map[path] = cgo
                # Tour will populate the cargo from the underlying file -
                # do not attempt sendfile on the OS layer.
                tour.res.direct_boarding = False
            else:
                if cgo._status == MemBargeDocker.MemCargo.LOADING:
                    # Cargo is loading; create a pipe so the multiplexer can
                    # wake the waiting tour when end_save runs.
                    BayLog.debug("%s Cannot start tour (file reading)", tour)
                    rfd, wfd = os.pipe()
                    os.set_blocking(rfd, False)
                    source_rd = IORudder(os.fdopen(rfd, "rb", buffering=0))
                    wait_rd = IORudder(os.fdopen(wfd, "wb", buffering=0))
                    cgo._add_waiter(wait_rd)
                else:
                    tour.res.direct_boarding = False

            cgo._access()
            return cgo, source_rd

    ######################################################
    # Private methods
    ######################################################

    def _add_total(self, length: int) -> None:
        with self._lock:
            self._total_size += length
            BayLog.debug("%s addTotal=%d", self, self._total_size)
            # Drop oldest entries until we're back under capacity. Skip
            # entries with active waiters (they would release later).
            while self._total_size > self.capacity_bytes and self._cargo_map:
                oldest_path, oldest = next(iter(self._cargo_map.items()))
                if not oldest._waiters:
                    BayLog.debug("%s Remove cargo: %s cur total=%d",
                                 self, oldest_path, self._total_size)
                    self._total_size -= oldest.length()
                    del self._cargo_map[oldest_path]
                else:
                    break
                BayLog.debug("%s cargo removed: total=%d", self, self._total_size)
