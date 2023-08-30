from bayserver_core.bay_log import BayLog
from bayserver_core.util.string_util import StringUtil

from bayserver_docker_fcgi.fcg_command import FcgCommand
from bayserver_docker_fcgi.fcg_type import FcgType


#
#  FCGI spec
#    http://www.mit.edu/~yandros/doc/specs/fcgi-spec.html
#
#
#  Params command format (Name-Value list)
#
#          typedef struct {
#              unsigned char nameLengthB0;  // nameLengthB0  >> 7 == 0
#              unsigned char valueLengthB0; // valueLengthB0 >> 7 == 0
#              unsigned char nameData[nameLength];
#              unsigned char valueData[valueLength];
#          } FCGI_NameValuePair11;
#
#          typedef struct {
#              unsigned char nameLengthB0;  // nameLengthB0  >> 7 == 0
#              unsigned char valueLengthB3; // valueLengthB3 >> 7 == 1
#              unsigned char valueLengthB2;
#              unsigned char valueLengthB1;
#              unsigned char valueLengthB0;
#              unsigned char nameData[nameLength];
#              unsigned char valueData[valueLength
#                      ((B3 & 0x7f) << 24) + (B2 << 16) + (B1 << 8) + B0];
#          } FCGI_NameValuePair14;
#
#          typedef struct {
#              unsigned char nameLengthB3;  // nameLengthB3  >> 7 == 1
#              unsigned char nameLengthB2;
#              unsigned char nameLengthB1;
#              unsigned char nameLengthB0;
#              unsigned char valueLengthB0; // valueLengthB0 >> 7 == 0
#              unsigned char nameData[nameLength
#                      ((B3 & 0x7f) << 24) + (B2 << 16) + (B1 << 8) + B0];
#              unsigned char valueData[valueLength];
#          } FCGI_NameValuePair41;
#
#          typedef struct {
#              unsigned char nameLengthB3;  // nameLengthB3  >> 7 == 1
#              unsigned char nameLengthB2;
#              unsigned char nameLengthB1;
#              unsigned char nameLengthB0;
#              unsigned char valueLengthB3; // valueLengthB3 >> 7 == 1
#              unsigned char valueLengthB2;
#              unsigned char valueLengthB1;
#              unsigned char valueLengthB0;
#              unsigned char nameData[nameLength
#                      ((B3 & 0x7f) << 24) + (B2 << 16) + (B1 << 8) + B0];
#              unsigned char valueData[valueLength
#                      ((B3 & 0x7f) << 24) + (B2 << 16) + (B1 << 8) + B0];
#          } FCGI_NameValuePair44;
#

class CmdParams(FcgCommand):

    def __init__(self, req_id):
        super().__init__(FcgType.PARAMS, req_id)
        self.params = []

    def __str__(self):
        return f"FcgCmdParams{self.params}"

    def unpack(self, pkt):
        super().unpack(pkt)
        acc = pkt.new_data_accessor()
        while acc.pos < pkt.data_len():
            name_len = self.read_length(acc)
            value_len = self.read_length(acc)

            name = bytearray(name_len)
            acc.get_bytes(name, 0, name_len)

            value = bytearray(value_len)
            acc.get_bytes(value, 0, value_len)

            name = StringUtil.from_bytes(name)
            value = StringUtil.from_bytes(value)
            BayLog.trace("Params: %s=%s", name, value)
            self.add_param(name, value)

    def pack(self, pkt):
        acc = pkt.new_data_accessor()
        for nv in self.params:
            name = nv[0]
            value = nv[1]
            name_len = len(name)
            value_len = len(value)

            self.write_length(name_len, acc)
            self.write_length(value_len, acc)

            acc.put_string(name)
            acc.put_string(value)

        # must be called from last line
        super().pack(pkt)

    def handle(self, cmd_handler):
        return cmd_handler.handle_params(self)


    #
    # private
    #
    def read_length(self, acc):
        len = acc.get_byte()
        if len >> 7 == 0:
            return len
        else:
            len2 = acc.get_byte()
            len3 = acc.get_byte()
            len4 = acc.get_byte()
            return ((len & 0x7f) << 24) | (len2 << 16) | (len3 << 8) | len4

    def write_length(self, length, acc):
        if length >> 7 == 0:
            acc.put_byte(length)
        else:
            buf = bytearray(4)
            buf[0] = (length >> 24 & 0xFF) | 0x80
            buf[1] = length >> 16 & 0xFF
            buf[2] = length >> 8 & 0xFF
            buf[3] = length & 0xFF
            acc.put_bytes(buf)

    def add_param(self, name, value):
        if name is None:
            raise RuntimeError("nil argument")

        if value is None:
            value = ""

        self.params.append([name, value])




