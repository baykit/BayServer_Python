import datetime
import os

from bayserver_core.bayserver import BayServer
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.headers import Headers

class CgiUtil:
    REQUEST_METHOD = "REQUEST_METHOD"
    REQUEST_URI = "REQUEST_URI"
    SERVER_PROTOCOL = "SERVER_PROTOCOL"
    GATEWAY_INTERFACE = "GATEWAY_INTERFACE"
    SERVER_NAME = "SERVER_NAME"
    SERVER_PORT = "SERVER_PORT"
    QUERY_STRING = "QUERY_STRING"
    SCRIPT_NAME = "SCRIPT_NAME"
    SCRIPT_FILENAME = "SCRIPT_FILENAME"
    PATH_TRANSLATED = "PATH_TRANSLATED"
    PATH_INFO = "PATH_INFO"
    CONTENT_TYPE = "CONTENT_TYPE"
    CONTENT_LENGTH = "CONTENT_LENGTH"
    REMOTE_ADDR = "REMOTE_ADDR"
    REMOTE_PORT = "REMOTE_PORT"
    REMOTE_USER = "REMOTE_USER"
    HTTP_ACCEPT = "HTTP_ACCEPT"
    HTTP_COOKIE = "HTTP_COOKIE"
    HTTP_HOST = "HTTP_HOST"
    HTTP_USER_AGENT = "HTTP_USER_AGENT"
    HTTP_ACCEPT_ENCODING = "HTTP_ACCEPT_ENCODING"
    HTTP_ACCEPT_LANGUAGE = "HTTP_ACCEPT_LANGUAGE"
    HTTP_CONNECTION = "HTTP_CONNECTION"
    HTTP_UPGRADE_INSECURE_REQUESTS = "HTTP_UPGRADE_INSECURE_REQUESTS"
    HTTPS = "HTTPS"
    PATH = "PATH"
    SERVER_SIGNATURE = "SERVER_SIGNATURE"
    SERVER_SOFTWARE = "SERVER_SOFTWARE"
    SERVER_ADDR = "SERVER_ADDR"
    DOCUMENT_ROOT = "DOCUMENT_ROOT"
    REQUEST_SCHEME = "REQUEST_SCHEME"
    CONTEXT_PREFIX = "CONTEXT_PREFIX"
    CONTEXT_DOCUMENT_ROOT = "CONTEXT_DOCUMENT_ROOT"
    SERVER_ADMIN = "SERVER_ADMIN"
    REQUEST_TIME_FLOAT = "REQUEST_TIME_FLOAT"
    REQUEST_TIME = "REQUEST_TIME"
    UNIQUE_ID = "UNIQUE_ID"
    X_FORWARDED_HOST = "X_FORWARDED_HOST"
    X_FORWARDED_FOR = "X_FORWARDED_FOR"
    X_FORWARDED_PROTO = "X_FORWARDED_PROTO"
    X_FORWARDED_PORT = "X_FORWARDED_PORT"

    @classmethod
    def get_env_hash(cls, path, doc_root, script_base, tur):

        env = {}

        def callback(name, value):
            env[name] = value

        CgiUtil.get_env(path, doc_root, script_base, tur, callback)

        return env


    @classmethod
    def get_env(cls, path, doc_root, script_base, tur, cb):

        req_headers = tur.req.headers

        ctype = req_headers.content_type()
        if StringUtil.is_set(ctype):
            pos = ctype.find("charset=")
            if pos >= 0:
                tur.req.charset = ctype[pos + 8:].strip()

        cls.add_env(CgiUtil.REQUEST_METHOD, tur.req.method, cb)
        cls.add_env(CgiUtil.REQUEST_URI, tur.req.uri, cb)
        cls.add_env(CgiUtil.SERVER_PROTOCOL, tur.req.protocol, cb)
        cls.add_env(CgiUtil.GATEWAY_INTERFACE, "CGI/1.1", cb)

        cls.add_env(CgiUtil.SERVER_NAME, tur.req.req_host, cb)
        cls.add_env(CgiUtil.SERVER_ADDR, tur.req.server_address, cb)
        if tur.req.req_port >= 0:
            cls.add_env(CgiUtil.SERVER_PORT, tur.req.req_port, cb)

        cls.add_env(CgiUtil.SERVER_SOFTWARE, BayServer.get_software_name(), cb)
        cls.add_env(CgiUtil.CONTEXT_DOCUMENT_ROOT, doc_root, cb)

        for name in tur.req.headers.names():
            newval = None
            for value in tur.req.headers.values(name):
                if newval is None:
                    newval = value
                else:
                    newval = newval + "; " + value

            name = name.upper().replace('-', '_')
            if name.startswith("X_FORWARDED_"):
                cls.add_env(name, newval, cb)
            else:
                if name == CgiUtil.CONTENT_TYPE or name ==  CgiUtil.CONTENT_LENGTH:
                    cls.add_env(name, newval, cb)
                else:
                    cls.add_env("HTTP_" + name, newval, cb)


        cls.add_env(CgiUtil.REMOTE_ADDR, tur.req.remote_address, cb)
        cls.add_env(CgiUtil.REMOTE_PORT, tur.req.remote_port, cb)

        cls.add_env(CgiUtil.REQUEST_SCHEME, "https" if tur.is_secure else "http", cb)
        tmp_secure = tur.is_secure
        fproto = tur.req.headers.get(Headers.X_FORWARDED_PROTO)
        if fproto is not None:
            tmp_secure = fproto.lower() == "https"

        if tmp_secure:
            cls.add_env(CgiUtil.HTTPS, "on", cb)

        cls.add_env(CgiUtil.QUERY_STRING, tur.req.query_string, cb)
        cls.add_env(CgiUtil.SCRIPT_NAME, tur.req.script_name, cb)
        cls.add_env(CgiUtil.UNIQUE_ID, str(datetime.datetime.now()), cb)

        if tur.req.path_info is None:
            cls.add_env(CgiUtil.PATH_INFO, "", cb)
        else:
            cls.add_env(CgiUtil.PATH_INFO, tur.req.path_info, cb)

            locpath = doc_root
            if locpath.endswith("/"):
                locpath = locpath[0:- 2]

            path_translated = locpath + tur.req.path_info
            cls.add_env(CgiUtil.PATH_TRANSLATED, path_translated, cb)

        if not script_base.endswith("/"):
            script_base = script_base + "/"

        cls.add_env(CgiUtil.SCRIPT_FILENAME, script_base + tur.req.script_name[len(path):], cb)
        cls.add_env(CgiUtil.PATH, os.getenv("PATH"), cb)

    @classmethod
    def add_env(cls, key, value, cb):
        if value is None:
            value = ""

        cb(key, str(value))
