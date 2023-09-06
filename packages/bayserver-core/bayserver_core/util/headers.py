import copy

from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil


class Headers:
    #
    # known header names
    #
    HEADER_SEPARATOR = ": "

    CONTENT_TYPE = "content-type"
    CONTENT_LENGTH = "content-length"
    CONTENT_ENCODING = "content-encoding"
    HDR_TRANSFER_ENCODING = "transfer-encoding"
    CONNECTION = "connection"
    AUTHORIZATION = "authorization"
    WWW_AUTHENTICATE = "www-authenticate"
    STATUS = "status"
    LOCATION = "location"
    HOST = "host"
    COOKIE = "cookie"
    USER_AGENT = "user-agent"
    ACCEPT = "accept"
    ACCEPT_LANGUAGE = "accept-language"
    ACCEPT_ENCODING = "accept-encoding"
    UPGRADE_INSECURE_REQUESTS = "upgrade-insecure-requests"
    SERVER = "Server"
    X_FORWARDED_HOST = "x-forwarded-host"
    X_FORWARDED_FOR = "x-forwarded-for"
    X_FORWARDED_PROTO = "x-forwarded-proto"
    X_FORWARDED_PORT = "x-forwarded-port"

    CONNECTION_CLOSE = 1
    CONNECTION_KEEP_ALIVE = 2
    CONNECTION_UPGRADE = 3
    CONNECTION_UNKOWN = 4

    def __init__(self):
        self.status = None
        self.headers = {}
        self.clear()

    def __str__(self):
        return f"Headers(s={self.status} h={self.headers}"

    def clear(self):
        self.headers.clear()
        self.status = HttpStatus.OK

    def copy_to(self, dst):
        dst.status = self.status
        for name in self.headers.keys():
            values = copy.copy(self.headers[name])
            dst.headers[name] = values

    def set_status(self, status):
        self.status = int(status)

    def get(self, name):
        values = self.headers.get(name.lower())
        if values is None:
            return None
        else:
            return values[0]

    def get_int(self, name):
        val = self.get(name)
        if val is None:
            return -1
        else:
            return int(val)

    def set(self, name, value):
        name = name.lower()
        values = self.headers.get(name)
        if values is None:
            values = []
            self.headers[name] = values
        values.clear()
        values.append(value)

    def set_int(self, name, value):
        self.set(name, str(value))

    def add(self, name, value):
        if not isinstance(name, str):
            raise BaseException("argument 1 is not a string")
        if not isinstance(value, str):
            raise BaseException("argument 2 is not a string")

        name = name.lower()
        values = self.headers.get(name)
        if values is None:
            values = []
            self.headers[name] = values

        values.append(value)

    def add_int(self, name, value):
        self.add(name, str(value))

    def names(self):
        return self.headers.keys()

    def values(self, name):
        values = self.headers.get(name.lower())
        if values is None:
            return []
        else:
            return values

    def count(self):
        c = 0
        for name in self.headers.keys():
            for value in self.values(name):
                c += 1

        return c

    def contains(self, name):
        return name.lower() in self.headers.keys()

    def remove(self, name):
        try:
            self.headers.pop(name.lower())
        except KeyError as e:
            pass

    #
    # Utility methods
    #
    def content_type(self):
        return self.get(Headers.CONTENT_TYPE)

    def set_content_type(self, type):
        self.set(Headers.CONTENT_TYPE, type)

    def content_length(self):
        length = self.get(Headers.CONTENT_LENGTH)
        if StringUtil.is_empty(length):
            return -1
        else:
            return int(length)

    def set_content_length(self, length):
        self.set_int(Headers.CONTENT_LENGTH, length)

    def get_connection(self):
        con = self.get(Headers.CONNECTION)
        if con is not None:
            con = con.lower()

        if con == "close":
            return Headers.CONNECTION_CLOSE
        elif con == "keep-alive":
            return Headers.CONNECTION_KEEP_ALIVE
        elif con == "upgrade":
            return Headers.CONNECTION_UPGRADE
        else:
            return Headers.CONNECTION_UNKOWN
