import traceback

from abc import ABCMeta, abstractmethod

from bayserver_core.bay_log import BayLog
from bayserver_core.common.vehicle import Vehicle
from bayserver_core.http_exception import HttpException
from bayserver_core.util.counter import Counter

class Train(Vehicle, metaclass=ABCMeta):

    #
    # abstract methods
    #
    @abstractmethod
    def depart(self):
        pass

    #
    # Class variables
    #
    train_id_counter = Counter()

    def __init__(self):
        super().__init__(Train.train_id_counter.next())

    def __str__(self):
        return f"train##{self.id}"

    def run(self):

        try:
            BayLog.debug("%s Start train", self)
            self.depart()

        except BaseException as e:
            BayLog.error_e(e, traceback.format_stack())

        BayLog.debug("%s End train", self)


