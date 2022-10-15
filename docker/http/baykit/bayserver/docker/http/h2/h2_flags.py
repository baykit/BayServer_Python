
class H2Flags:
    FLAGS_NONE = 0x0
    FLAGS_ACK = 0x1
    FLAGS_END_STREAM = 0x1
    FLAGS_END_HEADERS = 0x4
    FLAGS_PADDED = 0x8
    FLAGS_PRIORITY = 0x20

    def __init__(self, flags=FLAGS_NONE):
        self.flags = flags

    def has_flag(self, flag):
        return (self.flags & flag) != 0


    def set_flag(self, flag, val):
        if val:
            self.flags |= flag
        else:
            self.flags &= ~flag

    def ack(self):
        return self.has_flag(H2Flags.FLAGS_ACK)

    def set_ack(self, val):
        self.set_flag(H2Flags.FLAGS_ACK, val)


    def end_stream(self):
        return self.has_flag(H2Flags.FLAGS_END_STREAM)


    def set_end_stream(self, val):
        self.set_flag(H2Flags.FLAGS_END_STREAM, val)


    def end_headers(self):
        return self.has_flag(H2Flags.FLAGS_END_HEADERS)

    def set_end_headers(self, val):
        self.set_flag(H2Flags.FLAGS_END_HEADERS, val)

    def padded(self):
        return self.has_flag(H2Flags.FLAGS_PADDED)

    def set_padded(self, val):
        self.set_flag(H2Flags.FLAGS_PADDED, val)


    def priority(self):
        return self.has_flag(H2Flags.FLAGS_PRIORITY)

    def set_priority(self, val):
        self.set_flag(H2Flags.FLAGS_PRIORITY, val)

    def __str__(self):
        return hex(self.flags)


