import time


class FileContent:
    """Cached file content held in memory."""

    path: str
    content: bytes
    loaded_time: float

    def __init__(self, path: str, content: bytes):
        self.path = path
        self.content = content
        self.loaded_time = time.time()
