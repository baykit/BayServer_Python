from bayserver_core.bcf.bcf_parser import BcfParser
from bayserver_core.bcf.bcf_key_val import BcfKeyVal

class HttpStatus:
    #
    # Known status
    #
    OK = 200
    MOVED_PERMANENTLY = 301
    MOVED_TEMPORARILY = 302
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    UPGRADE_REQUIRED = 426
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504
    HTTP_VERSION_NOT_SUPPORTED = 505

    status = {}
    initialized = False

    @classmethod
    def init(cls, bcf_file):
        if HttpStatus.initialized:
            return

        p = BcfParser()
        doc = p.parse(bcf_file)
        for kv in doc.content_list:
            if isinstance(kv, BcfKeyVal):
                HttpStatus.status[int(kv.key)] = kv.value

        HttpStatus.initialized = True

    @classmethod
    def description(cls, status_code):
        desc = HttpStatus.status.get(status_code)
        if desc is None:
            return str(status_code)
        else:
            return desc