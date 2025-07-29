from typing import Dict

from bayserver_core.agent.lifecycle_listener import LifecycleListener
from bayserver_core.bay_log import BayLog

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.util.object_store import ObjectStore
from bayserver_core.util.string_util import StringUtil

class ProtocolHandlerStore(ObjectStore):
    class AgentListener(LifecycleListener):

        def add(self, agt):
            for ifo in ProtocolHandlerStore.proto_map.values():
                ifo.add_agent(agt)

        def remove(self, agt):
            for ifo in ProtocolHandlerStore.proto_map.values():
                ifo.remove_agent(agt)


    class ProtocolInfo:
        def __init__(self, proto, svr_mode, proto_hnd_factory):
            self.protocol = proto
            self.server_mode = svr_mode
            self.protocol_handler_factory = proto_hnd_factory

            # Agent ID => ProtocolHandlerStore
            self.stores = {}

        def add_agent(self, agt_id: int):
            store = PacketStore.get_store(self.protocol, agt_id);
            self.stores[agt_id] = ProtocolHandlerStore(self.protocol, self.server_mode,
                                                             self.protocol_handler_factory, store);

        def remove_agent(self, agt_id: int):
            del self.stores[agt_id]

    proto_map: Dict[str, ProtocolInfo] = None

    def __init__(self, proto, svr_mode, proto_hnd_factory, pkt_store):
        ObjectStore.__init__(self)
        self.protocol = proto
        self.server_mode = svr_mode
        self.factory = lambda : \
            proto_hnd_factory.create_protocol_handler(pkt_store)


    def print_usage(self, indent):
        BayLog.info("%sProtocolHandlerStore(%s%s) Usage:", StringUtil.indent(indent), self.protocol, "s" if self.server_mode else "c")
        super().print_usage(indent+1)

    ######################################################
    # class methods
    ######################################################
    @classmethod
    def init(cls):
        if cls.proto_map is None:
            cls.proto_map = {}
            GrandAgent.add_lifecycle_listener(ProtocolHandlerStore.AgentListener())


    @classmethod
    def get_store(cls, protocol: str, svr_mode: bool, agent_id: int):
        return ProtocolHandlerStore.proto_map[ProtocolHandlerStore.construct_protocol(protocol, svr_mode)].stores[agent_id]


    @classmethod
    def get_stores(cls, agent_id):
        store_list = []
        for ifo in ProtocolHandlerStore.proto_map.values():
            store_list.append(ifo.stores[agent_id])
        return store_list


    @classmethod
    def register_protocol(cls, protocol, svr_mode, proto_hnd_factory):
        #BayLog.debug("register protocol: proto=%s server_mode=%s", protocol, svr_mode)
        if ProtocolHandlerStore.construct_protocol(protocol, svr_mode) not in ProtocolHandlerStore.proto_map.keys():
            ProtocolHandlerStore.proto_map[ProtocolHandlerStore.construct_protocol(protocol, svr_mode)] = \
                ProtocolHandlerStore.ProtocolInfo(protocol, svr_mode, proto_hnd_factory)

    @classmethod
    def construct_protocol(cls, protocol, svr_mode):
        if svr_mode:
            return protocol + "-s"
        else:
            return protocol + "-c"
