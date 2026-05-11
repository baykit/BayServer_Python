from bayserver_core.protocol.protocol_exception import ProtocolException


class HeaderBlock:
    INDEX = 1
    OVERLOAD_KNOWN_HEADER = 2
    NEW_HEADER = 3
    KNOWN_HEADER = 4
    UNKNOWN_HEADER = 5
    UPDATE_DYNAMIC_TABLE_SIZE = 6

    # RFC 7541 default for SETTINGS_HEADER_TABLE_SIZE; BayServer does not
    # currently advertise a different value in its initial SETTINGS frame.
    MAX_DYNAMIC_TABLE_SIZE = 4096

    def __init__(self):
        self.op = None
        self.index = None
        self.name = None
        self.value = None
        self.size = None

    def __str__(self):
        return f"{self.op} index={self.index} name={self.name} value={self.value}"

    @classmethod
    def pack(cls, blk, acc):
        if blk.op == HeaderBlock.INDEX:
            acc.put_hpack_int(blk.index, 7, 1)

        elif blk.op == HeaderBlock.OVERLOAD_KNOWN_HEADER:
            raise RuntimeError("IllegalState")

        elif blk.op == HeaderBlock.NEW_HEADER:
            raise RuntimeError("Illegal State")

        elif blk.op == HeaderBlock.KNOWN_HEADER:
            acc.put_hpack_int(blk.index, 4, 0)
            acc.put_hpack_string(blk.value, False)

        elif blk.op == HeaderBlock.UNKNOWN_HEADER:
            acc.put_byte(0)
            acc.put_hpack_string(blk.name, False)
            acc.put_hpack_string(blk.value, False)

        elif blk.op == HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE:
            raise RuntimeError("Illegal state")


    @classmethod
    def unpack(cls, acc):
        blk = HeaderBlock()
        index = acc.get_byte()
        is_index_header_field = (index & 0x80) != 0
        if is_index_header_field:
            # index header field
            #   0   1   2   3   4   5   6   7
            # +---+---+---+---+---+---+---+---+
            # | 1 |        Index (7+)         |
            # +---+---------------------------+
            blk.op = HeaderBlock.INDEX
            blk.index = index & 0x7F
            # RFC 7541 § 6.1: index 0 is not used and MUST be treated as a decoding error.
            if blk.index == 0:
                raise ProtocolException("Indexed header field with index 0")

        else:
            # literal header field
            update_index = (index & 0x40) != 0
            if update_index:
                index = index & 0x3F
                overload_index = (index != 0)
                if overload_index:
                    if index == 0x3F:
                        index = index + acc.get_hpack_int_rest()

                    blk.op = HeaderBlock.OVERLOAD_KNOWN_HEADER
                    blk.index = index
                    #   0   1   2   3   4   5   6   7
                    # +---+---+---+---+---+---+---+---+
                    # | 0 | 1 |      Index (6+)       |
                    # +---+---+-----------------------+
                    # | H |     Value Length (7+)     |
                    # +---+---------------------------+
                    # | Value String (Length octets)  |
                    # +-------------------------------+
                    blk.value = acc.get_hpack_string()
                else:
                    # new header name
                    #   0   1   2   3   4   5   6   7
                    # +---+---+---+---+---+---+---+---+
                    # | 0 | 1 |           0           |
                    # +---+---+-----------------------+
                    # | H |     Name Length (7+)      |
                    # +---+---------------------------+
                    # |  Name String (Length octets)  |
                    # +---+---------------------------+
                    # | H |     Value Length (7+)     |
                    # +---+---------------------------+
                    # | Value String (Length octets)  |
                    # +-------------------------------+
                    blk.op = HeaderBlock.NEW_HEADER
                    blk.name = acc.get_hpack_string()
                    blk.value = acc.get_hpack_string()

            else:
                update_dynamic_table_size = (index & 0x20) != 0
                if update_dynamic_table_size:
                    #   0   1   2   3   4   5   6   7
                    # +---+---+---+---+---+---+---+---+
                    # | 0 | 0 | 1 |   Max size (5+)   |
                    # +---+---------------------------+
                    size = index & 0x1F
                    if size == 0x1F:
                        size = size + acc.get_hpack_int_rest()

                    # RFC 7541 § 6.3: the dynamic table size update must not exceed
                    # SETTINGS_HEADER_TABLE_SIZE (RFC default 4096).
                    if size > HeaderBlock.MAX_DYNAMIC_TABLE_SIZE:
                        raise ProtocolException(
                            f"Dynamic table size update {size} exceeds "
                            f"SETTINGS_HEADER_TABLE_SIZE {HeaderBlock.MAX_DYNAMIC_TABLE_SIZE}")
                    blk.op = HeaderBlock.UPDATE_DYNAMIC_TABLE_SIZE
                    blk.size = size
                else:
                    # not update index
                    index = (index & 0xF)
                    if index != 0:
                        #   0   1   2   3   4   5   6   7
                        # +---+---+---+---+---+---+---+---+
                        # | 0 | 0 | 0 | 0 |  Index (4+)   |
                        # +---+---+-----------------------+
                        # | H |     Value Length (7+)     |
                        # +---+---------------------------+
                        # | Value String (Length octets)  |
                        # +-------------------------------+
                        #
                        # OR
                        #
                        #   0   1   2   3   4   5   6   7
                        # +---+---+---+---+---+---+---+---+
                        # | 0 | 0 | 0 | 1 |  Index (4+)   |
                        # +---+---+-----------------------+
                        # | H |     Value Length (7+)     |
                        # +---+---------------------------+
                        # | Value String (Length octets)  |
                        # +-------------------------------+
                        if index == 0xF:
                            index = index + acc.get_hpack_int_rest()

                        blk.op = HeaderBlock.KNOWN_HEADER
                        blk.index = index
                        blk.value = acc.get_hpack_string()
                    else:
                        # literal header field
                        #   0   1   2   3   4   5   6   7
                        # +---+---+---+---+---+---+---+---+
                        # | 0 | 0 | 0 | 0 |       0       |
                        # +---+---+-----------------------+
                        # | H |     Name Length (7+)      |
                        # +---+---------------------------+
                        # |  Name String (Length octets)  |
                        # +---+---------------------------+
                        # | H |     Value Length (7+)     |
                        # +---+---------------------------+
                        # | Value String (Length octets)  |
                        # +-------------------------------+
                        #
                        # OR
                        #
                        #   0   1   2   3   4   5   6   7
                        # +---+---+---+---+---+---+---+---+
                        # | 0 | 0 | 0 | 1 |       0       |
                        # +---+---+-----------------------+
                        # | H |     Name Length (7+)      |
                        # +---+---------------------------+
                        # |  Name String (Length octets)  |
                        # +---+---------------------------+
                        # | H |     Value Length (7+)     |
                        # +---+---------------------------+
                        # | Value String (Length octets)  |
                        # +-------------------------------+
                        #
                        blk.op = HeaderBlock.UNKNOWN_HEADER
                        blk.name = acc.get_hpack_string()
                        blk.value = acc.get_hpack_string()

        return blk





