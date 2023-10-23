import time
from abc import ABCMeta, abstractmethod
import threading
from time import sleep

from bayserver_core.sink import Sink
from bayserver_core.bay_log import BayLog
from bayserver_core.agent.next_socket_action import NextSocketAction

class SpinHandler:

    class SpinListener(metaclass=ABCMeta):
        @abstractmethod
        def lap(self, spun):
            pass

        @abstractmethod
        def checkTimeout(self, duration_sec):
            pass

        @abstractmethod
        def close(self):
            pass

    class ListenerInfo:
        def __init__(self, lis, last_access):
            self.listener = lis
            self.last_access = last_access

    def __init__(self, agt):
        self.listeners = []
        self.lock = threading.RLock()
        self.agent = agt
        self.spin_count = 0

        agt.add_timer_handler(self)

    def __str__(self):
        return str(self.agent)


    ######################################################
    # Implements TimerHandler
    ######################################################

    def on_timer(self):
        self.stop_timeout_spins()

    ######################################################
    # Custom methods
    ######################################################

    def process_data(self):
        if len(self.listeners) == 0:
            return False

        all_spun = True
        remove_list = []
        for i in reversed(range(0, len(self.listeners))):
            lis = self.listeners[i].listener
            (act, spun) = lis.lap()

            if act == NextSocketAction.SUSPEND:
                remove_list.append(i)
            elif act == NextSocketAction.CLOSE:
                remove_list.append(i)
            elif act == NextSocketAction.CONTINUE:
                continue
            else:
                raise Sink("Invalid next state")

            self.listeners[i].last_access = time.time();
            all_spun = all_spun & spun

        if all_spun:
            self.spin_count += 1
            if self.spin_count > 10:
                sleep(0.01)
        else:
            self.spin_count = 0

        for i in remove_list:
            with self.lock:
                self.listeners.pop(i)

        return True

    def ask_to_callback(self, lis):
        BayLog.debug("%s Ask to callback: %s", self, lis);

        found = False
        for ifo in self.listeners:
            if ifo.listener == lis:
                found = True
                break

        if found:
            BayLog.error("Already registered")
        else:
            with self.lock:
                self.listeners.append(SpinHandler.ListenerInfo(lis, time.time()))


    def is_empty(self):
        return len(self.listeners) == 0


    def stop_timeout_spins(self):
        if len(self.listeners) == 0:
            return

        remove_list = []
        with self.lock:
            now = time.time()
            for i in reversed(range(0, len(self.listeners))):
                ifo = self.listeners[i]
                if ifo.listener.check_timeout(int(now - ifo.last_access)):
                    ifo.listener.close()
                    remove_list += i

        for i in remove_list:
            with self.lock:
                self.listeners.pop(i)
