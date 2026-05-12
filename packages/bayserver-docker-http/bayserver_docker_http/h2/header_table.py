from bayserver_core.util.key_val import KeyVal

class HeaderTable:
    PSEUDO_HEADER_AUTHORITY = ":authority"
    PSEUDO_HEADER_METHOD = ":method"
    PSEUDO_HEADER_PATH = ":path"
    PSEUDO_HEADER_SCHEME = ":scheme"
    PSEUDO_HEADER_STATUS = ":status"

    static_table = None
    static_size = 0

    # RFC 7541 §4.1 entry overhead: every dynamic-table entry's size is
    # name.len + value.len + 32. The default max table byte size (= 4096)
    # caps the encoder/decoder agreement so the dynamic table doesn't
    # grow unbounded over a long-lived H2 connection. Without enforcement
    # idx_map.insert(0, ...) on an unbounded list is O(N) head-insert,
    # which compounds quadratically.
    _ENTRY_OVERHEAD = 32
    _DEFAULT_MAX_BYTES = 4096

    def __init__(self):
        self.idx_map = []
        self.add_count = 0
        self.name_map = {}
        self.cur_byte_size = 0
        self.max_byte_size = HeaderTable._DEFAULT_MAX_BYTES

    def get(self, idx):
        if idx <= 0 or idx > HeaderTable.static_size + len(self.idx_map):
            raise RuntimeError(f"idx={idx} static={HeaderTable.static_size} dynamic={len(self.idx_map)}")

        if idx <= HeaderTable.static_size:
            kv = HeaderTable.static_table.idx_map[idx - 1]
        else:
            kv = self.idx_map[(idx - HeaderTable.static_size) - 1]

        return kv

    def get_idx_list(self, name):
        dynamic_list = self.name_map.get(name)
        static_list = HeaderTable.static_table.name_map.get(name)

        idx_list = []
        if static_list is not None:
            idx_list += static_list

        if dynamic_list is not None:
            for idx in dynamic_list:
                real_index = self.add_count - idx + HeaderTable.static_size
                idx_list.append(real_index)

        return idx_list

    def insert(self, name, value):
        sz = self._entry_size(name, value)
        # Evict oldest entries until the new one fits (RFC 7541 §4.4).
        # idx_map stores newest-first (idx_map[0] is most recent), so the
        # oldest entry sits at idx_map[-1].
        while self.idx_map and self.cur_byte_size + sz > self.max_byte_size:
            evicted = self.idx_map.pop()
            self.cur_byte_size -= self._entry_size(evicted.name, evicted.value)
        if sz > self.max_byte_size:
            # RFC 7541 §4.4: an entry alone exceeding the max size empties
            # the table and is not inserted. add_count is still bumped so
            # encoder/decoder agree on numbering.
            self.add_count += 1
            return
        self.idx_map.insert(0, KeyVal(name, value))
        self.cur_byte_size += sz
        self.add_count += 1
        self.add_to_name_map(name, self.add_count)

    def set_size(self, size):
        # SETTINGS_HEADER_TABLE_SIZE: bound the table in bytes. If the new
        # max is below cur_byte_size, evict from the tail.
        self.max_byte_size = size
        while self.idx_map and self.cur_byte_size > self.max_byte_size:
            evicted = self.idx_map.pop()
            self.cur_byte_size -= self._entry_size(evicted.name, evicted.value)

    @staticmethod
    def _entry_size(name, value):
        return ((len(name) if name else 0)
                + (len(value) if value else 0)
                + HeaderTable._ENTRY_OVERHEAD)

    def put(self, idx, name, value):
        if idx != len(self.idx_map) + 1:
            raise RuntimeError("Illegal State")

        self.idx_map.append(KeyVal(name, value))
        self.add_to_name_map(name, idx)

    #
    # private
    #

    def add_to_name_map(self, name, idx):
        idx_list = self.name_map.get(name)
        if idx_list is None:
            idx_list = []
            self.name_map[name] = idx_list

        idx_list.append(idx)

    @classmethod
    def create_dynamic_table(cls):
        t = HeaderTable()
        return t


# 
# class initializer
# 

HeaderTable.static_table = HeaderTable()

HeaderTable.static_table.put(1, HeaderTable.PSEUDO_HEADER_AUTHORITY, "")
HeaderTable.static_table.put(2, HeaderTable.PSEUDO_HEADER_METHOD, "GET")
HeaderTable.static_table.put(3, HeaderTable.PSEUDO_HEADER_METHOD, "POST")
HeaderTable.static_table.put(4, HeaderTable.PSEUDO_HEADER_PATH, "/")
HeaderTable.static_table.put(5, HeaderTable.PSEUDO_HEADER_PATH, "/index.html")
HeaderTable.static_table.put(6, HeaderTable.PSEUDO_HEADER_SCHEME, "http")
HeaderTable.static_table.put(7, HeaderTable.PSEUDO_HEADER_SCHEME, "https")
HeaderTable.static_table.put(8, HeaderTable.PSEUDO_HEADER_STATUS, "200")
HeaderTable.static_table.put(9, HeaderTable.PSEUDO_HEADER_STATUS, "204")
HeaderTable.static_table.put(10, HeaderTable.PSEUDO_HEADER_STATUS, "206")
HeaderTable.static_table.put(11, HeaderTable.PSEUDO_HEADER_STATUS, "304")
HeaderTable.static_table.put(12, HeaderTable.PSEUDO_HEADER_STATUS, "400")
HeaderTable.static_table.put(13, HeaderTable.PSEUDO_HEADER_STATUS, "404")
HeaderTable.static_table.put(14, HeaderTable.PSEUDO_HEADER_STATUS, "500")
HeaderTable.static_table.put(15, "accept-charset", "")
HeaderTable.static_table.put(16, "accept-encoding", "gzip, deflate")
HeaderTable.static_table.put(17, "accept-language", "")
HeaderTable.static_table.put(18, "accept-ranges", "")
HeaderTable.static_table.put(19, "accept", "")
HeaderTable.static_table.put(20, "access-control-allow-origin", "")
HeaderTable.static_table.put(21, "age", "")
HeaderTable.static_table.put(22, "allow", "")
HeaderTable.static_table.put(23, "authorization", "")
HeaderTable.static_table.put(24, "cache-control", "")
HeaderTable.static_table.put(25, "content-disposition", "")
HeaderTable.static_table.put(26, "content-encoding", "")
HeaderTable.static_table.put(27, "content-language", "")
HeaderTable.static_table.put(28, "content-length", "")
HeaderTable.static_table.put(29, "content-location", "")
HeaderTable.static_table.put(30, "content-range", "")
HeaderTable.static_table.put(31, "content-type", "")
HeaderTable.static_table.put(32, "cookie", "")
HeaderTable.static_table.put(33, "date", "")
HeaderTable.static_table.put(34, "etag", "")
HeaderTable.static_table.put(35, "expect", "")
HeaderTable.static_table.put(36, "expires", "")
HeaderTable.static_table.put(37, "from", "")
HeaderTable.static_table.put(38, "host", "")
HeaderTable.static_table.put(39, "if-match", "")
HeaderTable.static_table.put(40, "if-modified-since", "")
HeaderTable.static_table.put(41, "if-none-match", "")
HeaderTable.static_table.put(42, "if-range", "")
HeaderTable.static_table.put(43, "if-unmodified-since", "")
HeaderTable.static_table.put(44, "last-modified", "")
HeaderTable.static_table.put(45, "link", "")
HeaderTable.static_table.put(46, "location", "")
HeaderTable.static_table.put(47, "max-forwards", "")
HeaderTable.static_table.put(48, "proxy-authenticate", "")
HeaderTable.static_table.put(49, "proxy-authorization", "")
HeaderTable.static_table.put(50, "range", "")
HeaderTable.static_table.put(51, "referer", "")
HeaderTable.static_table.put(52, "refresh", "")
HeaderTable.static_table.put(53, "retry-after", "")
HeaderTable.static_table.put(54, "server", "")
HeaderTable.static_table.put(55, "set-cookie", "")
HeaderTable.static_table.put(56, "strict-transport-security", "")
HeaderTable.static_table.put(57, "transfer-encoding", "")
HeaderTable.static_table.put(58, "user-agent", "")
HeaderTable.static_table.put(59, "vary", "")
HeaderTable.static_table.put(60, "via", "")
HeaderTable.static_table.put(61, "www-authenticate", "")

HeaderTable.static_size = len(HeaderTable.static_table.idx_map)


