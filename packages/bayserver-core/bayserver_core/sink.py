from bayserver_core.bay_log import BayLog


class Sink(Exception):

    def __init__(self, fmt=None, *args):
        if fmt is None:
            msg = ""
        elif len(args) == 0:
            msg = "%s" % fmt
        else:
            try:
                msg = fmt % args
            except TypeError as e:
                BayLog.error_e(e)
                msg = fmt

        super().__init__(msg + "(>_<)")
