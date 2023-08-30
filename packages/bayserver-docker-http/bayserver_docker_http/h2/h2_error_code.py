from bayserver_core.bayserver import BayServer
from bayserver_core.util.locale import Locale
from bayserver_core.util.message import Message


class H2ErrorCode(Message):
    NO_ERROR = 0x0
    PROTOCOL_ERROR = 0x1
    INTERNAL_ERROR = 0x2
    FLOW_CONTROL_ERROR = 0x3
    SETTINGS_TIMEOUT = 0x4
    STREAM_CLOSED = 0x5
    FRAME_SIZE_ERROR = 0x6
    REFUSED_STREAM = 0x7
    CANCEL = 0x8
    COMPRESSION_ERROR = 0x9
    CONNECT_ERROR = 0xa
    ENHANCE_YOUR_CALM = 0xb
    INADEQUATE_SECURITY = 0xc
    HTTP_1_1_REQUIRED = 0xd

    desc = {}
    msg = None

    @classmethod
    def init_codes(cls):
        if H2ErrorCode.msg is not None:
            return

        prefix = BayServer.bserv_lib + "/conf/h2_messages"
        H2ErrorCode.msg = H2ErrorCode()
        H2ErrorCode.msg.init(prefix, Locale('ja', 'JP'))
