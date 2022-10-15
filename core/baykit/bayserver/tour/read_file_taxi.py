import threading
from baykit.bayserver.bay_log import BayLog

from baykit.bayserver.sink import Sink
from baykit.bayserver.agent.next_socket_action import NextSocketAction
from baykit.bayserver.util.valve import Valve
from baykit.bayserver.taxi.taxi_runner import TaxiRunner
from baykit.bayserver.taxi.taxi import Taxi


class ReadFileTaxi(Taxi, Valve):

    def __init__(self, buf_size):
        super().__init__()
        self.infile = None
        self.ch_valid = None
        self.data_listener = None
        self.buf = None
        self.running = None
        self.buf_size = buf_size
        self.lock = threading.RLock()



    def init(self, infile, data_listener):
        self.data_listener = data_listener;
        self.infile = infile
        self.ch_valid = True


    def __str__(self):
        return Taxi.__str__(self) + " " + str(self.data_listener)


    ######################################################
    # implements Valve
    ######################################################

    def open_valve(self):
        with self.lock:
            self.next_run()

    ######################################################
    # implements Taxi
    ######################################################

    def depart(self):
        with self.lock:
            try:
                if not self.ch_valid:
                    raise Sink()

                buf = self.infile.read(self.buf_size)

                if len(buf) == 0:
                    self.data_listener.notify_eof()
                    self.close()
                    return

                act = self.data_listener.notify_read(buf, None)

                self.running = False
                if act == NextSocketAction.CONTINUE:
                    self.next_run()

            except BaseException as e:
                BayLog.error_e(e)
                self.close()

    def next_run(self):
        if self.running:
            # If running, not posted because next run exists
            #raise Sink("%s already running", self)
            return

        self.running = True
        TaxiRunner.post(self)


    def close(self):
        self.ch_valid = False
        self.infile.close()
        self.data_listener.notify_close()

