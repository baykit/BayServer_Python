from bayserver_core.bay_exception import BayException
from bayserver_core.util.http_status import HttpStatus

class HttpException(BayException):
    def __init__(self, status, fmt=None, *args):
        super().__init__(self.add_status_to_message(status, fmt), *args)
        self.status = status
        self.location = None
        if status < 300 or status >= 600:
            raise Exception("Illegal Http error status code: %d", status)

    def add_status_to_message(self, status, fmt):
        if fmt is None:
            return f"{status}"
        else:
            return f"{status} {fmt}"

    @classmethod
    def moved_temp(cls, location):
        e = HttpException(HttpStatus.MOVED_TEMPORARILY, location)
        e.location = location
        return e
