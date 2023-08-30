from abc import ABCMeta, abstractmethod

import threading

from bayserver_core.bay_log import BayLog
from bayserver_core.util.counter import Counter


class Taxi(metaclass=ABCMeta):

    #
    # abstract method
    #
    @abstractmethod
    def depart(self):
        pass

    taxi_id_counter = Counter()

    def __init__(self):
        self.taxi_id = Taxi.taxi_id_counter.next()


    def __str__(self):
        return f"Taxi#{self.taxi_id}"

    def run(self):
        try:
            BayLog.trace("%s Start taxi on: %s", self, threading.currentThread().name);
            self.depart();
            BayLog.trace("%s End taxi on: %s", self, threading.currentThread().name);
        except BaseException as e:
            BayLog.error_e(e)
