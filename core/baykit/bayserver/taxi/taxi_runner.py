from concurrent.futures import ThreadPoolExecutor

from baykit.bayserver.bay_log import BayLog

class TaxiRunner:

    exe = None

    @classmethod
    def init(cls, num_agents):
        cls.exe = ThreadPoolExecutor(num_agents, "TaxiRunner")

    @classmethod
    def post(cls, taxi):
        try:
            cls.exe.submit(TaxiRunner.run, taxi)
            return True
        except BaseException as e:
            BayLog.error_e(e)
            return False


    @classmethod
    def run(cls, taxi):
        taxi.run()
