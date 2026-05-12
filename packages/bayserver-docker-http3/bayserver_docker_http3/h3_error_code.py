class H3ErrorCode:
    """RFC 9114 § 8.1 application error codes (subset used by the inbound
    handler). The Java port uses a Message lookup table for human-readable
    strings; in Python we keep the constants and let BayLog format the int
    directly."""

    NO_ERROR = 0x100
    GENERAL_PROTOCOL_ERROR = 0x101
    INTERNAL_ERROR = 0x102
    STREAM_CREATION_ERROR = 0x103
    CLOSED_CRITICAL_STREAM = 0x104
    FRAME_UNEXPECTED = 0x105
    FRAME_ERROR = 0x106
    EXCESSIVE_LOAD = 0x107
    ID_ERROR = 0x108
    SETTINGS_ERROR = 0x109
    MISSING_SETTINGS = 0x10a
    REQUEST_REJECTED = 0x10b
    REQUEST_CANCELLED = 0x10c
    REQUEST_INCOMPLETE = 0x10d
    MESSAGE_ERROR = 0x10e
    CONNECT_ERROR = 0x10f
    VERSION_FALLBACK = 0x110

    @staticmethod
    def get_message(code):
        return f"H3 0x{code:x}"
