import threading

from bayserver_core.bay_log import BayLog

from bayserver_core.taxi.taxi import Taxi
from bayserver_core.taxi.taxi_runner import TaxiRunner
from bayserver_core.util.valve import Valve

class WriteFileTaxi(Taxi, Valve):

    def __init__(self):
        super().__init__()
        self.outfile = None
        self.ch_valid = None
        self.data_listener = None
        self.lock = None
        self.write_queue = []
        self.lock = threading.Lock()
        self.agent_id = None

    def init(self, agt_id, out, data_listener):
        self.agent_id = agt_id
        self.outfile = out
        self.data_listener = data_listener
        self.ch_valid = True

    def __str__(self):
        return Taxi.__str__(self) + " " + str(self.data_listener)

    ######################################################
    # Implements Resumable
    ######################################################

    def open_valve(self):
        self.next_run()

    ######################################################
    # Implements Taxi
    ######################################################

    def depart(self):
        try:
            while True:
                with self.lock:
                    if len(self.write_queue) == 0:
                        break
                    buf = self.write_queue[0]
                    self.write_queue.pop(0)

                self.outfile.write(buf)

                with self.lock:
                    empty = len(self.write_queue) == 0

                if not empty:
                    self.next_run()

        except BaseException as e:
            BayLog.error_e(e)

    def post(self, buf, adr, tag):
        with self.lock:
            empty = len(self.write_queue) == 0
            self.write_queue.append(buf)
            if empty:
                self.open_valve()

    def next_run(self):
        TaxiRunner.post(self.agent_id, self)
        