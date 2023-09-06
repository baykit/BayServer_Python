from bayserver_core.bay_log import BayLog


class ProtocolException(IOError):
    def __init__(self, fmt, *args):
        if fmt is None:
            msg = ""
        elif len(args) == 0:
            msg = fmt
        else:
            try:
                msg = fmt % args
            except TypeError as e:
                BayLog.error_e(e)
                msg = fmt
        super().__init__(msg)