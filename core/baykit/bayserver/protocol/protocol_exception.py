class ProtocolException(IOError):
    def __init__(self, fmt, *args):
        if fmt is None:
            msg = ""
        elif args is None:
            msg = "%s" % fmt
        else:
            msg = fmt % args
        super().__init__(msg)