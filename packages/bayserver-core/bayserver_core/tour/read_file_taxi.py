import io
import os
import threading
import time

from bayserver_core.bay_log import BayLog

from bayserver_core.sink import Sink
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.util.valve import Valve
from bayserver_core.taxi.taxi_runner import TaxiRunner
from bayserver_core.taxi.taxi import Taxi


class ReadFileTaxi(Taxi, Valve):

    def __init__(self, agt, buf_size):
        super().__init__()
        self.agent = agt
        self.infile = None
        self.fd = None
        self.ch_valid = None
        self.data_listener = None
        self.buf = None
        self.running = None
        self.buf_size = buf_size
        self.lock = threading.RLock()
        self.start_time = None



    def init(self, infile, data_listener):
        if isinstance(infile, io.IOBase):
            self.infile = infile
            self.fd = infile.fileno()
        else:
            self.fd = infile
        self.data_listener = data_listener
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
        self.start_time = time.time()
        try:
            if not self.ch_valid:
                raise Sink()

            buf = os.read(self.fd, self.buf_size)

            if len(buf) == 0:
                self.close()
                return

            act = self.data_listener.notify_read(buf, None)

            self.running = False
            if act == NextSocketAction.CONTINUE:
                self.next_run()

        except IOError as e:
            BayLog.debug_e(e)
            self.close()

        except BaseException as e:
            BayLog.error_e(e)
            self.close()
            raise e

    def on_timer(self):
        duration_sec = int(time.time() - self.start_time)
        if self.data_listener.check_timeout(duration_sec):
            self.close()

    def next_run(self):
        if self.running:
            # If running, not posted because next run exists
            #raise Sink("%s already running", self)
            return

        self.running = True
        TaxiRunner.post(self.agent.agent_id, self)


    def close(self):
        with self.lock:
            if not self.ch_valid:
                return

            self.ch_valid = False
            self.data_listener.notify_eof()
            try:
                if isinstance(self.infile, io.IOBase):
                    self.infile.close()
                else:
                    os.close(self.fd)
            except:
                pass
            self.data_listener.notify_close()

