import signal

class SignalProxy:
    @classmethod
    def register(cls, sig, handler):
        signal.signal(sig, lambda signum, frame: handler())

