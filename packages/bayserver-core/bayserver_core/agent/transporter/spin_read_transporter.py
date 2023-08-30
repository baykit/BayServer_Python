from bayserver_core.bay_log import BayLog

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.spin_handler import SpinHandler
from bayserver_core.util.valve import Valve

class SpinReadTransporter(SpinHandler.SpinListener, Valve):


    def __init__(self, buf_size):
        self.spin_handler = None
        self.data_listener = None
        self.infile = None
        self.file_len = None
        self.read_buf = None
        self.total_read = None
        self.buf_size = buf_size
        self.timeout_sec = None
        self.eof_checker = None
        self.is_closed = False

    def init(self, spin_hnd, lis, infile, limit, timeout_sec, eof_checker):
        self.spin_handler = spin_hnd
        self.data_listener = lis
        self.infile = infile
        self.file_len = limit
        self.total_read = 0
        self.timeout_sec = timeout_sec
        self.eof_checker = eof_checker
        self.is_closed = False

    def __str__(self):
        return f"spinRead {self.data_listener} read={self.total_read} len={self.file_len}"


    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        self.data_listener = None
        self.infile = None

    ######################################################
    # Implements SpinListener
    ######################################################

    def lap(self):
        try:
            try:
                read_buf = self.infile.read(self.buf_size)
            except BlockingIOError as e:
                return (NextSocketAction.CONTINUE, True)

            if read_buf is None:
                # Python's bug?
                read_buf = ""
            self.total_read += len(read_buf)

            eof = False
            if len(read_buf) == 0:
                if self.eof_checker:
                    eof = self.eof_checker()

                if not eof:
                    BayLog.debug("%s Spin read: No stream data", self)
                    return (NextSocketAction.CONTINUE, True)
                else:
                    BayLog.debug("%s Spin read: EOF\\(^o^)/", self)

            if not eof:
                next_act = self.data_listener.notify_read(read_buf, None)

                if self.file_len == -1 or self.total_read < self.file_len:
                    return (next_act, False)

            # EOF
            self.data_listener.notify_eof()
            self.close()
            return (NextSocketAction.CLOSE, False)

        except BaseException as e:
            BayLog.error_e(e)
            self.close()
            return (NextSocketAction.CLOSE, False)


    def check_timeout(self, duration_sec):
        return duration_sec > self.timeout_sec

    def close(self):
        if self.infile:
            self.infile.close()
        self.data_listener.notify_close()
        self.is_closed = True

    ######################################################
    # Implements Valve
    ######################################################

    def open_valve(self):
        if not self.is_closed:
            self.spin_handler.ask_to_callback(self)

    ######################################################
    # Other methods
    ######################################################

