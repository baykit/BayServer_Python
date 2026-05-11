from bayserver_core.protocol.protocol_exception import ProtocolException


class H2ProtocolException(ProtocolException):
    """A ProtocolException that carries the specific HTTP/2 error code
    that should appear in the resulting GOAWAY frame. The base class always
    maps to H2ErrorCode.PROTOCOL_ERROR; this subclass lets call sites pick
    FLOW_CONTROL_ERROR, COMPRESSION_ERROR, REFUSED_STREAM, etc."""

    def __init__(self, error_code, message):
        super().__init__(message)
        self.error_code = error_code
