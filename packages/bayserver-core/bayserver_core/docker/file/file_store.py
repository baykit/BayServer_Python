import collections
import threading
import time

from bayserver_core.bay_log import BayLog
from bayserver_core.docker.file.file_content import FileContent


class FileStore:
    """In-memory cache of static file contents, bounded by total size and
    entry lifespan. Entries are loaded synchronously on first access and
    evicted when expired (or when adding would exceed `limit_bytes` and
    no expired entries can be reclaimed).
    """

    limit_bytes: int
    lifespan_sec: int

    def __init__(self, lifespan_sec: int, limit_bytes: int):
        self.lifespan_sec = lifespan_sec
        self.limit_bytes = limit_bytes
        self._total_bytes = 0
        self._contents = collections.OrderedDict()
        self._lock = threading.Lock()

    def has_cached(self, path: str) -> bool:
        """Return True iff `path` is currently present (and not expired) in the
        cache. Allows callers to skip a stat(2) on a cache hit (Java cf1b87b).
        """
        with self._lock:
            fc = self._contents.get(path)
            if fc is None:
                return False
            if fc.loaded_time + self.lifespan_sec < time.time():
                return False
            return True

    def get(self, path: str, file_len: int):
        """Return bytes when the file is cached (or freshly loaded).
        Returns None when the file does not fit in the cache."""
        with self._lock:
            now = time.time()
            fc = self._contents.get(path)
            if fc is not None:
                if fc.loaded_time + self.lifespan_sec < now:
                    BayLog.debug("Remove expired content: %s", path)
                    self._total_bytes -= len(fc.content)
                    del self._contents[path]
                    fc = None
                else:
                    # LRU touch
                    self._contents.move_to_end(path)
                    return fc.content

            if file_len > self.limit_bytes:
                return None

            if self._total_bytes + file_len > self.limit_bytes:
                if not self._evict(now, file_len):
                    return None

            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError as e:
                BayLog.debug("Cannot read file for cache: %s (%s)", path, e)
                return None

            fc = FileContent(path, data)
            self._contents[path] = fc
            self._total_bytes += len(data)
            return data

    def _evict(self, now: float, required: int) -> bool:
        """Evict expired entries (oldest first). Returns True when enough
        space has been reclaimed to fit `required` more bytes."""
        evicted = False
        for path in list(self._contents.keys()):
            if self._total_bytes + required <= self.limit_bytes:
                break
            fc = self._contents[path]
            if fc.loaded_time + self.lifespan_sec < now:
                BayLog.debug("Remove expired content: %s", path)
                self._total_bytes -= len(fc.content)
                del self._contents[path]
                evicted = True
            else:
                # Entries are insertion-ordered; the first non-expired one
                # means all following entries are younger, so stop.
                break
        return evicted
