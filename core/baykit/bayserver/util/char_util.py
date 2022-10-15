class CharUtil:
    CR = "\r"
    LF = "\n"

    CR_BYTE = ord("\r")
    LF_BYTE = ord("\n")
    SPACE_BYTE = ord(" ")
    COLON_BYTE = ord(":")
    CRLF_BYTES = bytearray([CR_BYTE, LF_BYTE])
    A_BYTE = ord("A")
    B_BYTE = ord("B")
    Z_BYTE = ord("Z")
    a_BYTE = ord("a")
    z_BYTE = ord("z")
    CASE_DIFF = a_BYTE - A_BYTE
    ENC_ASCII = "us-ascii"

    @classmethod
    def is_ascii(cls, c):
        cp = ord(c)
        return cp >= 32 and cp <= 126

    @classmethod
    def lower(cls, c):
        if c >= CharUtil.A_BYTE and c <= CharUtil.Z_BYTE:
            c += CharUtil.CASE_DIFF
        return c

    @classmethod
    def upper(cls, c):
        if c >= CharUtil.a_BYTE and c <= CharUtil.z_BYTE:
            c -= CharUtil.CASE_DIFF
        return c


