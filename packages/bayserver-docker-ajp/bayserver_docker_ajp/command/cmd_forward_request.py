from bayserver_core.bay_log import BayLog
from bayserver_docker_ajp.ajp_command import AjpCommand
from bayserver_docker_ajp.ajp_type import AjpType

from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.headers import Headers

#
#  AJP protocol
#     https://tomcat.apache.org/connectors-doc/ajp/ajpv13a.html
#
#  AJP13_FORWARD_REQUEST :=
#      prefix_code      (byte) 0x02 = JK_AJP13_FORWARD_REQUEST
#      method           (byte)
#      protocol         (string)
#      req_uri          (string)
#      remote_addr      (string)
#      remote_host      (string)
#      server_name      (string)
#      server_port      (integer)
#      is_ssl           (boolean)
#      num_headers      (integer)
#      request_headers(req_header_name req_header_value)
#      attributes     (attribut_name attribute_value)
#      request_terminator (byte) OxFF
#

class CmdForwardRequest(AjpCommand):
    method_map = None
    well_known_header_map = None
    attribute_name_map = None

    method_map = {
        1: "OPTIONS",
        2: "GET",
        3: "HEAD",
        4: "POST",
        5: "PUT",
        6: "DELETE",
        7: "TRACE",
        8: "PROPFIND",
        9: "PROPPATCH",
        10: "MKCOL",
        11: "COPY",
        12: "MOVE",
        13: "LOCK",
        14: "UNLOCK",
        15: "ACL",
        16: "REPORT",
        17: "VERSION_CONTROL",
        18: "CHECKIN",
        19: "CHECKOUT",
        20: "UNCHECKOUT",
        21: "SEARCH",
        22: "MKWORKSPACE",
        23: "UPDATE",
        24: "LABEL",
        25: "MERGE",
        26: "BASELINE_CONTROL",
        27: "MKACTIVITY",
    }

    @classmethod
    def get_method_code(cls, method):
        for key in CmdForwardRequest.method_map.keys():
            if cls.method_map[key].lower() == method.lower():
                return key


        return -1

    well_known_header_map = {
        0xA001: "Accept",
        0xA002: "Accept-Charset",
        0xA003: "Accept-Encoding",
        0xA004: "Accept-Language",
        0xA005: "Authorization",
        0xA006: "Connection",
        0xA007: "Content-Type",
        0xA008: "Content-Length",
        0xA009: "Cookie",
        0xA00A: "Cookie2",
        0xA00B: "Host",
        0xA00C: "Pragma",
        0xA00D: "Referer",
        0xA00E: "User-Agent",
    }

    @classmethod
    def get_well_known_header_code(cls, name):
        for key in cls.well_known_header_map.keys():
            if cls.well_known_header_map[key].lower() == name.lower():
                return key

        return -1

    attribute_name_map = {
        0x01: "?context",
        0x02: "?servlet_path",
        0x03: "?remote_user",
        0x04: "?auth_type",
        0x05: "?query_string",
        0x06: "?route",
        0x07: "?ssl_cert",
        0x08: "?ssl_cipher",
        0x09: "?ssl_session",
        0x0A: "?req_attribute",
        0x0B: "?ssl_key_size",
        0x0C: "?secret",
        0x0D: "?stored_method",
    }

    @classmethod
    def get_attribute_code(cls, atr):
        for key in cls.attribute_name_map.keys():
            if cls.attribute_name_map[key].lower() == atr.lower():
                return key

        return -1



    def __init__(self):
        super().__init__(AjpType.FORWARD_REQUEST, True)
        self.method = None
        self.protocol = None
        self.req_uri = None
        self.remote_addr = None
        self.remote_host = None
        self.server_name = None
        self.server_port = None
        self.is_ssl = None
        self.headers = Headers()
        self.attributes = {}


    def __str__(self):
        return f"ForwardRequest(m={self.method} p={self.protocol} u={self.req_uri} ra={self.remote_addr} rh={self.remote_host} sn={self.server_name} sp={self.server_port} ss={self.is_ssl} h={self.headers}"


    def pack(self, pkt):
        #BayLog.info("%s", self)
        acc = pkt.new_ajp_data_accessor()
        acc.put_byte(self.type)  # prefix code
        acc.put_byte(CmdForwardRequest.get_method_code(self.method))
        acc.put_string(self.protocol)
        acc.put_string(self.req_uri)
        acc.put_string(self.remote_addr)
        acc.put_string(self.remote_host)
        acc.put_string(self.server_name)
        acc.put_short(self.server_port)
        acc.put_byte(1 if self.is_ssl else 0)
        self.write_request_headers(acc)
        self.write_attributes(acc)

        #  must be called from last line
        super().pack(pkt)

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_ajp_data_accessor()
        acc.get_byte()  # prefix code
        self.method = CmdForwardRequest.method_map.get(acc.get_byte())
        self.protocol = acc.get_string()
        self.req_uri = acc.get_string()
        self.remote_addr = acc.get_string()
        self.remote_host = acc.get_string()
        self.server_name = acc.get_string()
        self.server_port = acc.get_short()
        self.is_ssl = acc.get_byte() == 1

        self.read_request_headers(acc)
        self.read_attributes(acc)

    def handle(self, handler):
        return handler.handle_forward_request(self)


    #
    # private
    #
    def read_request_headers(self, acc):
        count = acc.get_short()
        for i in range(count):
            code = acc.get_short()

            if code >= 0xA000:
                name = CmdForwardRequest.well_known_header_map.get(code)

                if name is None:
                    raise ProtocolException("Invalid header")

            else:
                # code is length of header name
                name = acc.get_string_by_len(code)

            value = acc.get_string()
            self.headers.add(name, value)
            # BayLog.trace "ForwardRequest header: #{name}=#{value}"

    def read_attributes(self, acc):
        while True:
            code = acc.get_byte()

            if code == 0xFF:
                break
            elif code == 0x0A:
                name = acc.get_string()
            else:
                name = CmdForwardRequest.attribute_name_map[code]
            if name is None:
                raise ProtocolException(f"Invalid attribute: code={code}")

            if code == 0x0B:  # "?ssl_key_size"
                value = acc.get_short()
                self.attributes[name] = str(value)
            else:
                value = acc.get_string()
                self.attributes[name] = value

    def write_request_headers(self, acc):
        h_list = []
        for name in self.headers.names():
            for value in self.headers.values(name):
                h_list.append([name, value])


        acc.put_short(len(h_list))
        for item in h_list:
            code = CmdForwardRequest.get_well_known_header_code(item[0])
            if code != -1:
                acc.put_short(code)
            else:
                acc.put_string(item[0])

            acc.put_string(item[1])

    def write_attributes(self, acc):
        for name in self.attributes.keys():
            value = self.attributes[name]
            code = CmdForwardRequest.get_attribute_code(name)
            if code != -1:
                acc.put_byte(code)
            else:
                acc.put_string(name)

            acc.put_string(value)

        acc.put_byte(0xFF)  # terminator code

