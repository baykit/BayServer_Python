from concurrent.futures import ThreadPoolExecutor
import threading

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.timer_handler import TimerHandler
from bayserver_core.bay_log import BayLog

class TaxiRunner(TimerHandler):

    class AgentListener(GrandAgent.GrandAgentLifecycleListener):
        def add(self, agt):
            TaxiRunner.runners[agt.agent_id] = TaxiRunner(agt)

        def remove(self, agt):
            TaxiRunner.runners[agt.agent_id].terminate()
            del TaxiRunner.runners[agt.agent_id]

    max_taxis = None
    runners = None
    runner = None

    def __init__(self, agt):
        self.agent = agt
        self.exe = ThreadPoolExecutor(TaxiRunner.max_taxis, f"TaxiRunner-{agt}-")
        self.running_taxi = None
        self.lock = threading.Lock()
        self.agent.add_timer_handler(self)

    def terminate(self):
        self.agent.remove_timer_handler(self)

    ######################################################
    # Implements TimerHandler
    ######################################################
    def on_timer(self):
        with(self.lock):
            if self.running_taxi is not None:
                self.running_taxi.on_timer()

    ######################################################
    # Class Methods
    ######################################################

    @classmethod
    def init(cls, max_taxis):
        cls.runners = {}
        cls.max_taxis = max_taxis
        GrandAgent.add_lifecycle_listener(TaxiRunner.AgentListener())

    @classmethod
    def post(cls, agt_id, taxi):
        BayLog.debug("Agt#%d post taxi: thread=%s taxi=%s", agt_id, threading.current_thread().name, taxi)
        try:
            cls.runners[agt_id].exe.submit(TaxiRunner.run, [agt_id, taxi])
            return True
        except BaseException as e:
            BayLog.error_e(e)
            return False

    @classmethod
    def run(cls, args):
        agt_id = args[0]
        taxi = args[1]
        runner = cls.runners[agt_id]
        BayLog.debug("Agt#%d Run taxi: thread=%s taxi=%s", agt_id, threading.current_thread().name, taxi)
        runner.running_taxi = taxi
        taxi.run()
        with runner.lock:
            runner.running_taxi = None

