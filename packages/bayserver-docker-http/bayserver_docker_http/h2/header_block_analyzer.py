from bayserver_docker_http.h2.header_block import HeaderBlock
from bayserver_docker_http.h2.header_table import HeaderTable


class HeaderBlockAnalyzer:
    
    def __init__(self):
        self.name = None
        self.value = None
        self.method = None
        self.path = None
        self.scheme = None
        self.status = None

    def clear(self):
        self.name = None
        self.value = None
        self.method = None
        self.path = None
        self.scheme = None
        self.status = None

    def analyze_header_block(self, blk, tbl):
        self.clear()
        if blk.op == HeaderBlock.INDEX:
            kv = tbl.get(blk.index)
            if (kv is None):
                raise RuntimeError(f"Invalid header index: {blk.index}")

            self.name = kv.name
            self.value = kv.value

        elif blk.op == HeaderBlock.KNOWN_HEADER or blk.op == HeaderBlock.OVERLOAD_KNOWN_HEADER:
            kv = tbl.get(blk.index)
            if (kv is None):
                raise RuntimeError(f"Invalid header index: {blk.index}")

            self.name = kv.name
            self.value = blk.value
            if (blk.op == HeaderBlock.OVERLOAD_KNOWN_HEADER):
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

        if self.name is not None and self.name[0] == ":":
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
