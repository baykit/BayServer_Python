from bayserver_core.bay_exception import BayException

class ConfigException(BayException):

    def __init__(self, file_name, line_no, fmt, *args):
        if fmt is None:
            msg = ""
        elif args is None:
            msg = "%s" % fmt
        else:
            msg = fmt % args

        super().__init__(ConfigException.create_message(msg, file_name, line_no))

        self.file_name = file_name
        self.line_no = line_no

    @classmethod
    def create_message(cls, msg, fname, line):
        return f"{'' if msg is None else msg} {fname}:{line}"
