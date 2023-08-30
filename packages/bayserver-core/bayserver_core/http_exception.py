from bayserver_core.bay_exception import BayException
from bayserver_core.util.http_status import HttpStatus

class HttpException(BayException):
    def __init__(self, status, fmt=None, *args):
        super().__init__(fmt, *args)
        self.status = status
        self.location = None
        if status < 300 or status >= 600:
            raise Exception("Illegal Http error status code: %d", status)

    def message(self):
        return f"HTTP {self.status} #{self.args[0]}"

    @classmethod
    def moved_temp(cls, location):
        e = HttpException(HttpStatus.MOVED_TEMPORARILY, location)
        e.location = location
        return e
