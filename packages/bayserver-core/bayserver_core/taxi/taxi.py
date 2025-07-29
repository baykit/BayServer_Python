from abc import ABCMeta, abstractmethod

import threading
import traceback

from bayserver_core.bay_log import BayLog
from bayserver_core.common.vehicle import Vehicle
from bayserver_core.util.counter import Counter


class Taxi(Vehicle, metaclass=ABCMeta):

    #
    # abstract method
    #
    @abstractmethod
    def depart(self):
        pass

    taxi_id_counter = Counter()

    def __init__(self):
        super().__init__(self.taxi_id_counter.next())


    def __str__(self):
        return f"Taxi#{self.id}"

    def run(self):
        try:
            BayLog.trace("%s Start taxi on: %s", self, threading.currentThread().name)
            self.depart()
            BayLog.trace("%s End taxi on: %s", self, threading.currentThread().name)
        except BaseException as e:
            BayLog.error_e(e, traceback.format_stack())
