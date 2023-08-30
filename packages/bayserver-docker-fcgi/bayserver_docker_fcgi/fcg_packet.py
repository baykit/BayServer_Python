from bayserver_core.protocol.packet import Packet

#
#  FCGI spec
#    http://www.mit.edu/~yandros/doc/specs/fcgi-spec.html
#
#  FCGI Packet (Record) format
#          typedef struct {
#              unsigned char version;
#              unsigned char type;
#              unsigned char requestIdB1;
#              unsigned char requestIdB0;
#              unsigned char contentLengthB1;
#              unsigned char contentLengthB0;
#              unsigned char paddingLength;
#              unsigned char reserved;
#              unsigned char contentData[contentLength];
#              unsigned char paddingData[paddingLength];
#          } FCGI_Record;
#

class FcgPacket(Packet):
    PREAMBLE_SIZE = 8

    VERSION = 1
    MAXLEN = 65535

    FCGI_NULL_REQUEST_ID = 0

    def __init__(self, type):
        super().__init__(type, FcgPacket.PREAMBLE_SIZE, FcgPacket.MAXLEN)
        self.version = FcgPacket.VERSION
        self.req_id = None

    def reset(self):
        super().reset()
        self.version = FcgPacket.VERSION
        self.req_id = 0

    def __str__(self):
        return f"FcgPacket({self.type}) id={self.req_id}"