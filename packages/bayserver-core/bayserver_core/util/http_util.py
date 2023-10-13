import binascii
import re
import base64
import socket

from bayserver_core.bay_log import BayLog

from bayserver_core.util.headers import Headers
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.char_util import CharUtil
from bayserver_core.util.exception_util import ExceptionUtil

class HttpUtil:
    MAX_LINE_LEN = 5000

    @classmethod
    def read_line(cls, file):
        # Current reading line
        buf = []

        n = 0
        eof = False
        while True:
            try:
                c = file.read(1)
            except EOFError as e:
                eof = True
                break

            c = c.decode("us-ascii")

            # If line is too long, return error
            if n >= HttpUtil.MAX_LINE_LEN:
                raise RuntimeError("Request line too long")

            # If character is newline, end to read line
            if c == "\n":
                break

            # Put the character to buffer
            buf.append(c)
            n += 1

        if n == 0 and eof:
            return None
        else:
            return "".join(buf).strip()

    #
    # Parse message headers
    #   message-header = field-name &quot;:&quot; [field-value]
    #
    @classmethod
    def parse_message_headers(self, file, header):
        while True:
            line = self.read_line(file)

            #  if line is empty ("\r\n")
            #  finish reading.
            if StringUtil.is_empty(line):
                break

            pos = line.find(":")
            if pos > 0:
                key = line[0:pos].strip()
                val = line[pos + 1:].strip()
                header.add(key, val)

    #
    # Send MIME headers This method is called from send_headers
    #
    @classmethod
    def send_mime_headers(cls, headers, buf):

        for name in headers.names():
            for value in headers.values(name):
                buf.put(StringUtil.to_bytes(name))
                buf.put([CharUtil.COLON_BYTE])
                buf.put(StringUtil.to_bytes(value))
                HttpUtil.send_new_line(buf)



    @classmethod
    def send_new_line(cls, buf):
        buf.put(CharUtil.CRLF_BYTES)

    @classmethod
    def parse_authorization(cls, tur):
        auth = tur.req.headers.get(Headers.AUTHORIZATION)
        if StringUtil.is_set(auth):
            ptn = r"Basic (.*)"
            result = re.match(ptn, auth)
            if result is None:
                BayLog.warn("Not matched with basic authentication format")
            else:
                try:
                    auth = result.group(1)
                    auth = base64.b64decode(auth).decode()
                    ptn = r"(.*):(.*)"
                    result = re.match(ptn, auth)
                except binascii.Error as e:
                    BayLog.warn_e(e, "decode error: %s", ExceptionUtil.message(e))

                if result is not None:
                    tur.req.remote_user = result.group(1)
                    tur.req.remote_pass = result.group(2)

    @classmethod
    def parse_host_port(cls, tur, default_port):
        tur.req.req_host = ""

        host_port = tur.req.headers.get(Headers.X_FORWARDED_HOST)
        if StringUtil.is_set(host_port):
            tur.req.headers.remove(Headers.X_FORWARDED_HOST)
            tur.req.headers.set(Headers.HOST, host_port)

        host_port = tur.req.headers.get(Headers.HOST)

        if StringUtil.is_set(host_port):
            pos = host_port.rfind(':')
            if pos == -1:
                tur.req.req_host = host_port
                tur.req.req_port = default_port
            else:
                tur.req.req_host = host_port[0: pos]
                try:
                    tur.req.req_port = int(host_port[pos + 1:])
                except BaseException as e:
                    BayLog.error(e)


    @classmethod
    def resolve_remote_host(cls, adr):
        if adr is None:
            return None

        try:
            return socket.gethostbyaddr(adr)[0]
        except OSError as e:
            BayLog.warn_e(e, "Cannot get remote host name: %s", e)
            return None
