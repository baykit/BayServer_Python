from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog

from bayserver_core.agent.grand_agent import GrandAgent

from bayserver_core.docker.base.inbound_ship_store import InboundShipStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.tour.tour_store import TourStore
from bayserver_core.docker.warp.warp_docker import WarpDocker
from bayserver_core.util.string_util import StringUtil

class MemUsage:

    class AgentListener(GrandAgent.GrandAgentLifecycleListener):

        def add(self, agt):
            MemUsage.mem_usages[agt.agent_id] = MemUsage(agt.agent_id)

        def remove(self, agt):
            del MemUsage.mem_usages[agt.agent_id]

    # Agent ID => MemUsage
    mem_usages = {}

    def __init__(self, agent_id):
        self.agent_id = agent_id

    def print_usage(self, indent):
        InboundShipStore.get_store(self.agent_id).print_usage(indent+1);
        for store in ProtocolHandlerStore.get_stores(self.agent_id):
          store.print_usage(indent+1)

        for store in PacketStore.get_stores(self.agent_id):
          store.print_usage(indent+1)

        TourStore.get_store(self.agent_id).print_usage(indent+1);
        for city in bs.BayServer.cities.cities:
            self.print_city_usage(None, city, indent)
        for port in bs.BayServer.port_docker_list:
            for city in port.cities.cities:
                self.print_city_usage(port, city, indent)


    def print_city_usage(self, port, city, indent):
        if port is None:
            pname = ""
        else:
            pname = f"@{port}"

        for club in city.clubs:
            if isinstance(club, WarpDocker):
                BayLog.info("%sClub(%s%s) Usage:", StringUtil.indent(indent), club, pname);
                club.get_ship_store(self.agent_id).print_usage(indent + 1);

        for town in city.towns:
            for club in town.clubs:
                if isinstance(club, WarpDocker):
                    BayLog.info("%sClub(%s%s) Usage:", StringUtil.indent(indent), club, pname);
                    club.get_ship_store(self.agent_id).print_usage(indent + 1);

    ######################################################
    # Class methods
    ######################################################
    @classmethod
    def init(cls):
        GrandAgent.add_lifecycle_listener(MemUsage.AgentListener());


    @classmethod
    def get(cls, agent_id):
        return MemUsage.mem_usages[agent_id]

    @classmethod
    def print_all_usages(cls):
        for i in range(bs.BayServer.harbor.grand_agents):
            BayLog.info("Agent#%d MemUsage", i+1);
            MemUsage.get(i+1).print_usage(1);