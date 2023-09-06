import datetime
import os.path
import sys
import traceback

from bayserver_core import bay_message
from bayserver_core.symbol import Symbol

class BayLog:
    LOG_LEVEL_TRACE = 0
    LOG_LEVEL_DEBUG = 1
    LOG_LEVEL_INFO = 2
    LOG_LEVEL_WARN = 3
    LOG_LEVEL_ERROR = 4
    LOG_LEVEL_FATAL = 5
    LOG_LEVEL_NAME = ["TRACE", "DEBUG", "INFO ", "WARN ", "ERROR", "FATAL"]

    log_level = LOG_LEVEL_INFO
    full_path = False

    @classmethod
    def set_log_level(cls, lvl):
        lvl = lvl.lower()
        if lvl == "trace":
            BayLog.log_level = BayLog.LOG_LEVEL_TRACE
        elif lvl == "debug":
            BayLog.log_level = BayLog.LOG_LEVEL_DEBUG
        elif lvl == "info":
            BayLog.log_level = BayLog.LOG_LEVEL_INFO
        elif lvl == "warn":
            BayLog.log_level = BayLog.LOG_LEVEL_WARN
        elif lvl == "error":
            BayLog.log_level = BayLog.LOG_LEVEL_ERROR
        elif lvl == "fatal":
            BayLog.log_level = BayLog.LOG_LEVEL_FATAL
        else:
            BayLog.warn(bay_message.BayMessage.get(Symbol.INT_UNKNOWN_LOG_LEVEL, lvl))

    @classmethod
    def set_full_path(cls, full_path):
        cls.full_path = full_path

    @classmethod
    def info(cls, fmt, *args):
        BayLog.log(BayLog.LOG_LEVEL_INFO, 3, None, fmt, args)

    @classmethod
    def info_e(cls, err, fmt=None, *args):
        BayLog.log(BayLog.LOG_LEVEL_INFO, 3, err, fmt, args)

    @classmethod
    def trace(cls, fmt, *args):
        BayLog.log(BayLog.LOG_LEVEL_TRACE, 3, None, fmt, args)

    @classmethod
    def debug(cls, fmt, *args):
        BayLog.log(BayLog.LOG_LEVEL_DEBUG, 3, None, fmt, args)

    @classmethod
    def debug_e(cls, err, fmt=None, *args):
        BayLog.log(BayLog.LOG_LEVEL_DEBUG, 3, err, fmt, args)

    @classmethod
    def warn(cls, fmt, *args):
        BayLog.log(BayLog.LOG_LEVEL_WARN, 3, None, fmt, args)

    @classmethod
    def warn_e(cls, err, fmt=None, *args):
        BayLog.log(BayLog.LOG_LEVEL_WARN, 3, err, fmt, args)

    @classmethod
    def error(cls, fmt, *args):
        BayLog.log(BayLog.LOG_LEVEL_ERROR, 3, None, fmt, args)

    @classmethod
    def error_e(cls, err, fmt=None, *args):
        BayLog.log(BayLog.LOG_LEVEL_ERROR, 3, err, fmt, args)

    @classmethod
    def fatal(cls, fmt, *args):
        BayLog.log(BayLog.LOG_LEVEL_FATAL, 3, None, fmt, args)

    @classmethod
    def fatal_e(cls, err, fmt=None, *args):
        BayLog.log(BayLog.LOG_LEVEL_FATAL, 3, err, fmt, args)
        exit(1)

    @classmethod
    def log(cls, lvl, stack_idx, err, fmt, args):
        if lvl < BayLog.log_level:
            return

        file, line = BayLog.get_caller(stack_idx)
        if not cls.full_path:
            file = os.path.basename(file)
        pos = f"File \"{file}\", line {line}"

        if fmt is not None:
            try:
                if args is None or len(args) == 0:
                    msg = "%s" % fmt
                else:
                    msg = fmt % args
            except BaseException as e:
                traceback.print_exc(file=sys.stdout)
                msg = fmt

            print(f"[{datetime.datetime.now()}] {BayLog.LOG_LEVEL_NAME[lvl]}. {msg} (at {pos})\n", file=sys.stdout, end="", flush=True)

        if err is not None:
            trc = traceback.format_exception_only(type(err), err)
            msg = trc[0].rstrip("\n")
            if True or BayLog.debug_mode() or lvl == BayLog.LOG_LEVEL_FATAL:
                print(type(err), file=sys.stdout)
                print(msg + " " + pos, file=sys.stdout)
                BayLog.print_exception(err)
            else:
                BayLog.log(lvl, 4, None, "%s", msg)

    @classmethod
    def debug_mode(cls):
        return BayLog.log_level <= BayLog.LOG_LEVEL_DEBUG

    @classmethod
    def trace_mode(cls):
        return BayLog.log_level == BayLog.LOG_LEVEL_TRACE

    @classmethod
    def print_exception(cls, err):
#        traceback.print_exc()
        try:
            raise err
        except:
            traceback.print_exc(file=sys.stdout)

    @classmethod
    def get_caller(cls, depth):
        try:
            raise Exception()
        except Exception as err:
            stk = traceback.extract_stack()
            st = stk[len(stk) - depth - 1]
            return st.filename, st.lineno
