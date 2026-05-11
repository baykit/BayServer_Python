from bayserver_core.protocol.protocol_exception import ProtocolException

from bayserver_docker_http.h2.header_block import HeaderBlock
from bayserver_docker_http.h2.header_table import HeaderTable


class HeaderBlockAnalyzer:

    def __init__(self):
        self.name = None
        self.value = None
        # The original header name before any renaming (e.g. :authority -> host).
        # Needed by pseudo-header validation that must distinguish :authority
        # from a literal "host" header the client might also send.
        self.raw_name = None
        self.method = None
        self.path = None
        self.scheme = None
        self.status = None
        # True iff raw_name started with ':' (i.e. this was a pseudo-header).
        self.pseudo = False

    def clear(self):
        self.name = None
        self.value = None
        self.raw_name = None
        self.method = None
        self.path = None
        self.scheme = None
        self.status = None
        self.pseudo = False

    def analyze_header_block(self, blk, tbl):
        self.clear()
        if blk.op == HeaderBlock.INDEX:
            # RFC 7541 § 2.3.3: indexed representation must reference a
            # valid entry; out-of-range indices are a decoding error.
            try:
                kv = tbl.get(blk.index)
            except (IndexError, ValueError) as e:
                raise ProtocolException(f"Invalid header index: {blk.index}")
            if kv is None:
                raise ProtocolException(f"Invalid header index: {blk.index}")
            self.name = kv.name
            self.value = kv.value

        elif blk.op == HeaderBlock.KNOWN_HEADER or blk.op == HeaderBlock.OVERLOAD_KNOWN_HEADER:
            try:
                kv = tbl.get(blk.index)
            except (IndexError, ValueError) as e:
                raise ProtocolException(f"Invalid header index: {blk.index}")
            if kv is None:
                raise ProtocolException(f"Invalid header index: {blk.index}")
            self.name = kv.name
            self.value = blk.value
            if blk.op == HeaderBlock.OVERLOAD_KNOWN_HEADER:
                tbl.insert(self.name, self.value)

        elif blk.op == HeaderBlock.NEW_HEADER:
            self.name = blk.name
            self.value = blk.value
            tbl.insert(self.name, self.value)

        elif blk.op == HeaderBlock.UNKNOWN_HEADER:
            self.name = blk.name
            self.value = blk.value

        elif blk.op == HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE:
            tbl.set_size(blk.size)

        else:
            raise RuntimeError("Illegal state")

        self.raw_name = self.name
        self.pseudo = self.name is not None and len(self.name) > 0 and self.name[0] == ":"

        if self.pseudo:
            if self.name == HeaderTable.PSEUDO_HEADER_AUTHORITY:
                self.name = "host"

            elif self.name == HeaderTable.PSEUDO_HEADER_METHOD:
                self.method = self.value

            elif self.name == HeaderTable.PSEUDO_HEADER_PATH:
                self.path = self.value

            elif self.name == HeaderTable.PSEUDO_HEADER_SCHEME:
                self.scheme = self.value

            elif self.name == HeaderTable.PSEUDO_HEADER_STATUS:
                self.status = self.value
