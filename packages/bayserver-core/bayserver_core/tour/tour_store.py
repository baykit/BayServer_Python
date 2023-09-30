#
# TourStore
#   You must lock object before call methods because all the methods may be called by different threads. (agent, tours agent)
#
import threading

from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.tour import tour

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.util.string_util import StringUtil

class TourStore:

    class AgentListener(GrandAgent.GrandAgentLifecycleListener):

        def add(self, agt):
            TourStore.stores[agt.agent_id] = TourStore()

        def remove(self, agt):
            del TourStore.stores[agt.agent_id]


    MAX_TOURS = 1024

    # class variables
    max_count = None

    # Agent ID => TourStore
    stores = {}

    def __init__(self):
        self.free_tours = []
        self.active_tour_map = {}
        self.lock = threading.Lock()


    def get(self, key):
        return self.active_tour_map.get(key)

    def rent(self, key, ship, force = False):
        tur = self.get(key)
        if tur is not None:
            raise Sink(f"{ship} Tour already exists")


        if len(self.free_tours) > 0:
            tur = self.free_tours.pop(-(len(self.free_tours) - 1))
        else:
            if not force and (len(self.active_tour_map) >= TourStore.max_count):
                BayLog.warn("Max tour count reached")
                return None
            else:
                tur = tour.Tour()

        self.active_tour_map[key] = tur
        return tur

    def Return(self, key):
        if key not in self.active_tour_map:
            raise Sink("Tour is not active: key=%d", key)

        tur = self.active_tour_map.pop(key)
        tur.reset()

        self.free_tours.append(tur)

    #
    # print memory usage
    #
    def print_usage(self, indent):
        BayLog.info("%sTour store usage:", StringUtil.indent(indent))
        BayLog.info("%sfreeList: %d", StringUtil.indent(indent + 1), len(self.free_tours))
        BayLog.info("%sactiveList: %d", StringUtil.indent(indent + 1), len(self.active_tour_map))
        if BayLog.debug_mode():
            for obj in self.active_tour_map.values():
                BayLog.debug("%s%s", StringUtil.indent(indent + 1), obj)


    ######################################################
    # class methods
    ######################################################
    @classmethod
    def init(cls, max_tours):
        TourStore.max_count = max_tours
        GrandAgent.add_lifecycle_listener(TourStore.AgentListener())

    @classmethod
    def get_store(cls, agent_id):
        return TourStore.stores[agent_id]
