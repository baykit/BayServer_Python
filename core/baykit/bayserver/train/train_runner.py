from concurrent.futures import ThreadPoolExecutor

from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.train.train import Train



class TrainRunner:



    @classmethod
    def init(cls, num_runners):
        TrainRunner.exe = ThreadPoolExecutor(num_runners, "TrainRunner")


    @classmethod
    def post(cls, train):
        try:
            TrainRunner.exe.submit(Train.run, train)
            return True
        except BaseException as e:
            BayLog.error_e(e)
            return False


