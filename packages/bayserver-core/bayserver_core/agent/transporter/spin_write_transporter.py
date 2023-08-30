import threading

from bayserver_core.bay_log import BayLog
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.spin_handler import SpinHandler
from bayserver_core.util.valve import Valve
from bayserver_core.util.postman import Postman


class SpinWriteTransporter(SpinHandler.SpinListener, Valve, Postman):

    def __init__(self):
        self.spin_handler = None
        self.data_listener = None
        self.outfile = None
        self.lock = None
        self.write_queue = []
        self.lock = threading.Lock()

    def init(self, spin_hnd, outfile, lis):
        self.spin_handler = spin_hnd
        self.data_listener = lis
        self.outfile = outfile

    def __str__(self):
        return str(self.data_listener)

    ######################################################
    # Implements Reusable
    ######################################################

    def reset(self):
        self.data_listener = None
        self.outfile = None

    ######################################################
    # Implements SpinListener
    ######################################################

    def lap(self):
        try:

            buf = None
            with self.lock:
                if len(self.write_queue) == 0:
                    BayLog.warn("%s Write queue empty", self)
                    return NextSocketAction.SUSPEND

                buf = self.write_queue[0]

            length = self.outfile.write(buf)

            if length == 0:
                return NextSocketAction.CONTINUE
            elif length < len(buf):
                buf[0:length] = ""
                return NextSocketAction.CONTINUE

            with self.lock:
                del self.write_queue[0]
                if len(self.write_queue) == 0:
                    return NextSocketAction.SUSPEND
                else:
                    return NextSocketAction.CONTINUE

        except Exception as e:
            BayLog.error_e(e)
            self.close()
            return NextSocketAction.CLOSE

    def check_timeout(self, duration_sec):
        return False

    def close(self):
        if self.outfile:
            self.outfile.close()

    ######################################################
    # Implements Valve
    ######################################################

    def open_valve(self):
        self.spin_handler.ask_to_callback(self)

    ######################################################
    # Other methods
    ######################################################

    def post(self, buf, tag):
        with self.lock:
            empty = len(self.write_queue) == 0
            self.write_queue.append(buf)
            if empty:
                self.open_valve()

