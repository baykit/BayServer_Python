import traceback

from bayserver_core.sink import Sink
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.char_util import CharUtil

from bayserver_docker_http.h1.h1_command import H1Command
from bayserver_docker_http.h1.h1_type import H1Type


#
# Header format
#
#        generic-message = start-line
#                           *(message-header CRLF)
#                           CRLF
#                           [ message-body ]
#        start-line      = Request-Line | Status-Line
#
#
#        message-header = field-name ":" [ field-value ]
#        field-name     = token
#        field-value    = *( field-content | LWS )
#        field-content  = <the OCTETs making up the field-value
#                         and consisting of either *TEXT or combinations
#                         of token, separators, and quoted-string>
#

class CmdHeader(H1Command):
    STATE_READ_FIRST_LINE = 1
    STATE_READ_MESSAGE_HEADERS = 2

    def __init__(self, is_req_header):
        H1Command.__init__(self, H1Type.HEADER)
        self.headers = []
        self.is_req_header = is_req_header
        self.method = None
        self.uri = None
        self.version = None
        self.status = None
        # Reusable scratch buffer for unpack_message_header. Sized lazily.
        self._parse_scratch = None

    def __str__(self):
        return "CommandHeader[H1]"


    @classmethod
    def new_req_header(cls, method, uri, version):
        h = CmdHeader(True)
        h.method = method
        h.uri = uri
        h.version = version
        return h

    @classmethod
    def new_res_header(cls, headers, version):
        h = CmdHeader(False)
        h.version = version
        h.status = headers.status
        for name in headers.names():
            for value in headers.values(name):
                h.add_header(name, value)

        return h


    def add_header(self, name, value):
        if name is None:
            raise Sink("name is nil")

        if value is None:
            BayLog.warn("Header value is nil: %s", name)
            return

        if not isinstance(name, str):
            BayLog.error("header name is not string: name=%s value=%s", name, value)
            raise Sink("IllegalArgument")

        if not isinstance(value, str):
            BayLog.error("header value is not string: name=%s value=%s", name, value)
            raise Sink("IllegalArgument")

        self.headers.append([name, value])


    def set_header(self, name, value):
        if name is None:
            raise Sink("Nil")

        if value is None:
            BayLog.warn("Header value is null: %s", name)
            return

        if not isinstance(name, str):
            raise Sink("IllegalArgument")

        if not isinstance(value, str):
            raise Sink("IllegalArgument")

        for nv in self.headers:
            if nv[0].lower() == name.lower():
                nv[1] = value
                return

        self.headers.append([name, value])

    def unpack(self, pkt):
        acc = pkt.new_data_accessor()
        data_len = pkt.data_len()
        state = CmdHeader.STATE_READ_FIRST_LINE

        line_start_pos = 0
        line_len = 0

        for pos in range(data_len):
            b = acc.get_byte()
            if b == CharUtil.CR_BYTE:
                continue
            elif b == CharUtil.LF_BYTE:
                if line_len == 0:
                    break

                if state == CmdHeader.STATE_READ_FIRST_LINE:
                    if self.is_req_header:
                        self.unpack_request_line(pkt.buf, line_start_pos, line_len)
                    else:
                        self.unpack_status_line(pkt.buf, line_start_pos, line_len)

                    state = CmdHeader.STATE_READ_MESSAGE_HEADERS

                else:
                    self.unpack_message_header(pkt.buf, line_start_pos, line_len)

                line_len = 0
                line_start_pos = pos + 1

            else:
                line_len += 1

        if state == CmdHeader.STATE_READ_FIRST_LINE:
            raise ProtocolException(
                BayMessage.get(
                    Symbol.HTP_INVALID_HEADER_FORMAT,
                    StringUtil.from_bytes(pkt.buf[line_start_pos: line_start_pos + line_len])))

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        if self.is_req_header:
            self.pack_request_line(acc)
        else:
            self.pack_status_line(acc)

        for nv in self.headers:
            self.pack_message_header(acc, nv[0], nv[1])

        self.pack_end_header(acc)

    def handle(self, cmd_handler):
        return cmd_handler.handle_header(self)


    ######################################################
    # Private methods
    ######################################################

    def unpack_request_line(self, buf, start, length):
        line = StringUtil.from_bytes(buf[start: start + length])
        items = line.split(" ")
        if len(items) != 3:
            raise ProtocolException(BayMessage.get(Symbol.HTP_INVALID_FIRST_LINE, line))

        self.method = items[0]
        self.uri = items[1]
        self.version = items[2]

    def unpack_status_line(self, buf, start, length):
        line = StringUtil.from_bytes(buf[start: start + length])
        items = line.split(" ")

        if len(items) < 2:
            raise ProtocolException(BayMessage.get(Symbol.HTP_INVALID_FIRST_LINE, line))

        self.version = items[0]

        try:
            self.status = int(items[1])
        except ValueError as e:
            BayLog.warn_e(e, traceback.format_stack(), "Invalid Status line")
            raise ProtocolException(BayMessage.get(Symbol.HTP_INVALID_FIRST_LINE, line))

    def  unpack_message_header(self, byte_array, start, length):
        # ASCII fast path on a reusable bytearray scratch. The previous
        # version allocated two fresh bytearrays per call (one for name,
        # one for value) and appended byte-by-byte. The Python loop is
        # already ASCII-only (CharUtil.lower folds A-Z only, no Unicode),
        # but the per-byte append + per-line alloc are the dominant
        # costs at small bodies on keep-alive.
        if self._parse_scratch is None or len(self._parse_scratch) < length:
            self._parse_scratch = bytearray(max(length, 64))
        buf = self._parse_scratch

        read_name = True
        skipping = True
        pos = 0
        colon_pos = -1
        SPACE = CharUtil.SPACE_BYTE
        TAB = 9
        COLON = CharUtil.COLON_BYTE
        A = CharUtil.A_BYTE
        Z = CharUtil.Z_BYTE
        DIFF = CharUtil.CASE_DIFF

        for i in range(length):
            b = byte_array[start + i]
            if skipping and (b == SPACE or b == TAB):
                continue
            if read_name and b == COLON:
                colon_pos = pos
                skipping = True
                read_name = False
                continue
            if read_name and A <= b <= Z:
                b += DIFF
            buf[pos] = b
            pos += 1
            skipping = False

        if colon_pos < 0:
            raise ProtocolException(
                BayMessage.get(
                    Symbol.HTP_INVALID_HEADER_FORMAT,
                    StringUtil.from_bytes(byte_array[start: start + length])))

        name = bytes(buf[:colon_pos])
        value = bytes(buf[colon_pos:pos])

        self.add_header(StringUtil.from_bytes(name), StringUtil.from_bytes(value))

    def pack_request_line(self, acc):
        acc.put_string(self.method)
        acc.put_byte(CharUtil.SPACE_BYTE)
        acc.put_string(self.uri)
        acc.put_byte(CharUtil.SPACE_BYTE)
        acc.put_string(self.version);
        acc.put_bytes(CharUtil.CRLF_BYTES)

    _H11_200 = "HTTP/1.1 200 OK\r\n".encode('us-ascii')
    _H10_200 = "HTTP/1.0 200 OK\r\n".encode('us-ascii')

    def pack_status_line(self, acc):
        if self.status == 200:
            if self.version is not None and self.version.upper() == "HTTP/1.1":
                acc.put_bytes(CmdHeader._H11_200)
            else:
                acc.put_bytes(CmdHeader._H10_200)
            return

        desc = HttpStatus.description(self.status)

        if self.version is not None and self.version.upper() == "HTTP/1.1":
            acc.put_string("HTTP/1.1")
        else:
            acc.put_string("HTTP/1.0")

        # status
        acc.put_byte(CharUtil.SPACE_BYTE)
        acc.put_string(str(self.status))
        acc.put_byte(CharUtil.SPACE_BYTE)
        acc.put_string(desc)
        acc.put_bytes(CharUtil.CRLF_BYTES)

    def pack_message_header(self, acc, name, value):
        if not isinstance(name, str):
            raise RuntimeError(f"IllegalArgument: {name}")

        if not isinstance(value, str):
            raise RuntimeError(f"IllegalArgument: {value}")


        acc.put_string(name)
        acc.put_byte(CharUtil.COLON_BYTE)
        acc.put_string(value)
        acc.put_bytes(CharUtil.CRLF_BYTES)

    def pack_end_header(self, acc):
        acc.put_bytes(CharUtil.CRLF_BYTES)
