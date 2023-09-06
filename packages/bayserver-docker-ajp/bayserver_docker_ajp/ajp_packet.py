from bayserver_core.protocol.packet import Packet
from bayserver_core.protocol.packet_part_accessor import PacketPartAccessor
from bayserver_core.util.string_util import StringUtil


#
#  AJP Protocol
#  https://tomcat.apache.org/connectors-doc/ajp/ajpv13a.html
#
#  AJP packet spec
#
#    packet:  preamble, length, body
#    preamble:
#         0x12, 0x34  (client->server)
#      | 'A', 'B'     (server->client)
#    length:
#       2 byte
#    body:
#       $length byte
#
#
#   Body format
#     client->server
#     Code     Type of Packet    Meaning
#        2     Forward Request   Begin the request-processing cycle with the following data
#        7     Shutdown          The web server asks the container to shut itself down.
#        8     Ping              The web server asks the container to take control (secure login phase).
#       10     CPing             The web server asks the container to respond quickly with a CPong.
#     none     Data              Size (2 bytes) and corresponding body data.
#
#     server->client
#     Code     Type of Packet    Meaning
#        3     Send Body Chunk   Send a chunk of the body from the servlet container to the web server (and presumably, onto the browser).
#        4     Send Headers      Send the response headers from the servlet container to the web server (and presumably, onto the browser).
#        5     End Response      Marks the end of the response (and thus the request-handling cycle).
#        6     Get Body Chunk    Get further data from the request if it hasn't all been transferred yet.
#        9     CPong Reply       The reply to a CPing request
#
#

class AjpPacket(Packet):

    class AjpAccessor(PacketPartAccessor):
        def __init__(self, pkt, start, max_len):
            super().__init__(pkt, start, max_len)

        def put_string(self, s):
            if StringUtil.is_empty(s):
                self.put_short(0xffff)
            else:
                self.put_short(len(s))
                super().put_string(s)
                self.put_byte(0)  # null terminator

        def get_string(self):
            return self.get_string_by_len(self.get_short())

        def get_string_by_len(self, length):

            if length == 0xffff:
                return ""

            buf = bytearray(length)
            self.get_bytes(buf, 0, length)
            self.get_byte()  # null terminator

            return StringUtil.from_bytes(buf)

    PREAMBLE_SIZE = 4
    MAX_DATA_LEN = 8192 - PREAMBLE_SIZE
    MIN_BUF_SIZE = 1024

    def __init__(self, typ):
        super().__init__(typ, AjpPacket.PREAMBLE_SIZE, AjpPacket.MAX_DATA_LEN)
        self.to_server = False

    def __str__(self):
        return f"AjpPacket({self.type})"

    def reset(self):
        super().reset()
        self.to_server = False

    def new_ajp_header_accessor(self):
        return AjpPacket.AjpAccessor(self, 0, AjpPacket.PREAMBLE_SIZE)

    def new_ajp_data_accessor(self):
        return AjpPacket.AjpAccessor(self, AjpPacket.PREAMBLE_SIZE, -1)

