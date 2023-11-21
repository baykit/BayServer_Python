from concurrent.futures import ThreadPoolExecutor
import threading

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.timer_handler import TimerHandler
from bayserver_core.bay_log import BayLog

class TaxiRunner(TimerHandler):

    class AgentListener(GrandAgent.GrandAgentLifecycleListener):
        def add(self, agt):
            TaxiRunner.runners[agt.agent_id - 1] = TaxiRunner(agt)

        def remove(self, agt):
            TaxiRunner.runners[agt.agent_id - 1].terminate()
            del TaxiRunner.runners[agt.agent_id - 1]

    max_taxis = None
    runners = None

    def __init__(self, agt):
        self.agent = agt
        self.exe = ThreadPoolExecutor(TaxiRunner.max_taxis, f"TaxiRunner-{agt}-")
        self.agent.add_timer_handler(self)
        self.running_taxis = []
        self.lock = threading.Lock()

    ######################################################
    # Implements TimerHandler
    ######################################################
    def on_timer(self):
        with(self.lock):
            for txi in self.running_taxis:
                txi.on_timer()

    ######################################################
    # Custom Methods
    ######################################################
    def terminate(self):
        self.agent.remove_timer_handler(self)

    def submit(self, txi):
        self.exe.submit(TaxiRunner.run, [self, txi])


    ######################################################
    # Class Methods
    ######################################################

    @classmethod
    def init(cls, max_taxis):
        cls.runners = {}
        cls.max_taxis = max_taxis
        GrandAgent.add_lifecycle_listener(TaxiRunner.AgentListener())

    @classmethod
    def post(cls, agt_id, txi):
        BayLog.debug("Agt#%d post taxi: thread=%s taxi=%s", agt_id, threading.current_thread().name, txi)
        try:
            cls.runners[agt_id - 1].submit(txi)
            return True
        except BaseException as e:
            BayLog.error_e(e)
            return False

    @classmethod
    def run(cls, args):
        runner = args[0]
        txi = args[1]

        with(runner.lock):
            runner.running_taxis.append(txi)

        BayLog.debug("%s Start taxi on thread=%s taxi=%s", runner.agent, threading.current_thread().name, txi)
        txi.run()

        with(runner.lock):
            runner.running_taxis.remove(txi)


