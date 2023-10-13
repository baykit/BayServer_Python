from bayserver_core import bay_log

class StringUtil:

    TRUES = ["yes", "true", "on", "1"]
    FALSES = ["no", "false", "off", "0"]

    @classmethod
    def is_set(cls, str):
        return str is not None and len(str) > 0

    @classmethod
    def is_empty(cls, str):
        return not StringUtil.is_set(str)


    @classmethod
    def eq_ignorecase(cls, a, b):
        if a is None or b is None:
            return False
        return a.lower() == b.lower()

    @classmethod
    def to_bytes(cls, s):
        try:
            return s.encode("us-ascii")
        except UnicodeEncodeError as e:
            bay_log.BayLog.warn("Cannot convert string to byte data (ignore): %s", s)
            return s.encode("utf-8", errors='replace')

    @classmethod
    def from_bytes(cls, byte_array):
        try:
            return byte_array.decode("us-ascii")
        except UnicodeDecodeError as e:
            bay_log.BayLog.warn("Cannot convert byte data to string (ignore): %s", str(byte_array))
            return byte_array.decode("utf-8", errors='replace')

    @classmethod
    def repeat(cls, str, times):
        return "".join([str] * times)

    @classmethod
    def indent(cls, count):
        return StringUtil.repeat(" ", count);


    @classmethod
    def parse_bool(cls, val):
        val = val.lower()
        if val in StringUtil.TRUES:
            return True

        if val in StringUtil.FALSES:
            return False

        else:
            bay_log.BayLog.warn("Invalid boolean value(set false): " + val)
            return False
