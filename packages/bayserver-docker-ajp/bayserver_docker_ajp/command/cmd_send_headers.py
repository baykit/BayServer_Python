from bayserver_core.bay_log import BayLog

from bayserver_docker_ajp.ajp_command import AjpCommand
from bayserver_docker_ajp.ajp_type import AjpType
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.http_status import HttpStatus

#
#  Send headers format
#
#  AJP13_SEND_HEADERS :=
#    prefix_code       4
#    http_status_code  (integer)
#    http_status_msg   (string)
#    num_headers       (integer)
#    response_headers *(res_header_name header_value)
#
#  res_header_name :=
#      sc_res_header_name | (string)   [see below for how this is parsed]
#
#  sc_res_header_name := 0xA0 (byte)
#
#  header_value := (string)
#

class CmdSendHeaders(AjpCommand):
    well_known_header_map = {}

    well_known_header_map = {
        "content-type": 0xA001,
        "content-language": 0xA002,
        "content-length": 0xA003,
        "date": 0xA004,
        "last-modified": 0xA005,
        "location": 0xA006,
        "set-cookie": 0xA007,
        "set-cookie2": 0xA008,
        "servlet-engine": 0xA009,
        "status": 0xA00A,
        "www-authenticate": 0xA00B,
    }

    @classmethod
    def get_well_known_header_name(cls, code):
        for name in cls.well_known_header_map.keys():
            if cls.well_known_header_map[name] == code:
                return name

        return None

    def __init__(self):
        super().__init__(AjpType.SEND_HEADERS, False)
        self.headers = {}
        self.status = HttpStatus.OK
        self.desc = None

    def __str__(self):
        return f"SendHeaders: s={self.status} d={self.desc} h={self.headers}"

    def pack(self, pkt):
        acc = pkt.new_ajp_data_accessor()
        acc.put_byte(self.type)
        acc.put_short(self.status)
        acc.put_string(HttpStatus.description(self.status))

        count = 0
        for key in self.headers.keys():
            count += len(self.headers[key])

        acc.put_short(count)

        for name in self.headers.keys():
            code = CmdSendHeaders.well_known_header_map.get(name)

            for value in self.headers[name]:
                if code is not None:
                    acc.put_short(code)
                else:
                    acc.put_string(name)

                acc.put_string(value)


        #  must be called from last line
        super().pack(pkt)

    def unpack(self, pkt):
        acc = pkt.new_ajp_data_accessor()
        prefix_code = acc.get_byte()
        if prefix_code != AjpType.SEND_HEADERS:
            raise ProtocolException("Expected SEND_HEADERS")

        self.status = acc.get_short()
        self.desc = acc.get_string()
        count = acc.get_short()
        for i in range(count):
            code = acc.get_short()
            name = CmdSendHeaders.get_well_known_header_name(code)
            if name is None:
                name = acc.get_string_by_len(code)

            value = acc.get_string()
            self.add_header(name, value)
        #BayLog.info("%s", self)

    def handle(self, handler):
        return handler.handle_send_headers(self)

    def get_header(self, name):
        values = self.headers.get(name.lower())
        if values is None or len(values) == 0:
            return None
        else:
            return values[0]

    def add_header(self, name, value):
        values = self.headers.get(name)
        if values is None:
            values = []
            self.headers[name] = values

        values.append(value)

