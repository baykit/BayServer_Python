import threading


class Counter:
    def __init__(self, ini=1):
        self.counter = ini
        self.lock = threading.RLock()

    def next(self):
        with self.lock:
                c = self.counter
                self.counter += 1
                return c
