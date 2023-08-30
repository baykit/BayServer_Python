from abc import ABCMeta, abstractmethod

from bayserver_core.bay_log import BayLog
from bayserver_core.http_exception import HttpException
from bayserver_core.util.counter import Counter

class Train(metaclass=ABCMeta):

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

    def __init__(self, tur):
        self.tour = tur
        self.tour_id = tur.id()
        self.train_id = Train.train_id_counter.next()

    def __str__(self):
        return f"train##{self.train_id}"

    def run(self):

        try:
            BayLog.debug("%s Start train (%s)", self, self.tour)
            self.depart()

        except HttpException as e:
            self.tour.res.send_http_exception(self.tour_id, e)

        except BaseException as e:
            BayLog.error_e(e)
            self.tour.res.end_content(self.tour_id)

        BayLog.debug("%s End train", self)


