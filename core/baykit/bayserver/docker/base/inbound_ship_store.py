from baykit.bayserver.bay_log import BayLog

from baykit.bayserver.agent.grand_agent import GrandAgent
from baykit.bayserver.docker.base.inbound_ship import InboundShip

from baykit.bayserver.util.string_util import StringUtil
from baykit.bayserver.util.object_store import ObjectStore

class InboundShipStore(ObjectStore):

    class AgentListener(GrandAgent.GrandAgentLifecycleListener):

        def add(self, agt):
            InboundShipStore.stores[agt.agent_id] = InboundShipStore()

        def remove(self, agt):
            del InboundShipStore.stores[agt.agent_id]

    stores = {}

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
        GrandAgent.add_lifecycle_listener(InboundShipStore.AgentListener())


    @classmethod
    def get_store(cls, agent_id):
        return InboundShipStore.stores[agent_id]
