class BayException(Exception):
    def __init__(self, fmt, *args):
        if not fmt:
            msg = None
        elif len(args) == 0:
            msg = "%s" % fmt
        else:
            msg = fmt % args

        super().__init__(msg)
