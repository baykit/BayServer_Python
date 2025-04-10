from typing import Dict

from bayserver_core.agent.lifecycle_listener import LifecycleListener
from bayserver_core.bay_log import BayLog

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.common.inbound_ship import InboundShip

from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.object_store import ObjectStore

class InboundShipStore(ObjectStore):

    class AgentListener(LifecycleListener):

        def add(self, agt_id: int):
            InboundShipStore.stores[agt_id] = InboundShipStore()

        def remove(self, agt_id: int):
            del InboundShipStore.stores[agt_id]

    stores: Dict[int, "InboundShipStore"] = None

    def __init__(self):
        super().__init__()
        self.factory = lambda: InboundShip()

    #
    #  print memory usage
    #
    def print_usage(self, indent):
        BayLog.info("%sInboundShipStore Usage:", StringUtil.indent(indent));
        super().print_usage(indent + 1);



    ######################################################
    # class methods
    ######################################################

    @classmethod
    def init(cls):
        if cls.stores is None:
            cls.stores = {}
            GrandAgent.add_lifecycle_listener(InboundShipStore.AgentListener())


    @classmethod
    def get_store(cls, agent_id: int):
        return InboundShipStore.stores[agent_id]
