from typing import Dict

from bayserver_core.agent import grand_agent as ga
from bayserver_core.agent.lifecycle_listener import LifecycleListener
from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.packet_factory import PacketFactory
from bayserver_core.util.object_store import ObjectStore
from bayserver_core.util.reusable import Reusable
from bayserver_core.util.string_util import StringUtil


class PacketStore(Reusable):
    class AgentListener(LifecycleListener):

        def add(self, agt_id: int):
            for ifo in PacketStore.proto_map.values():
                ifo.add_agent(agt_id)

        def remove(self, agt_id: int):
            for ifo in PacketStore.proto_map.values():
                ifo.remove_agent(agt_id)


    class ProtocolInfo:
        protocol: str
        stores: Dict[int, "PacketStore"]
        packet_factory: PacketFactory

        def __init__(self, proto, pkt_factory):
            self.protocol = proto

            # Agent ID => PacketStore
            self.stores = {}

            self.packet_factory = pkt_factory

        def add_agent(self, agt_id: int):
            store = PacketStore(self.protocol, self.packet_factory);
            self.stores[agt_id] = store


        def remove_agent(self, agt_id: int):
            BayLog.info(f"ProtocolInfo[{self.protocol}]: Removing agent {agt_id}")
            store = self.stores[agt_id]
            del self.stores[agt_id]


    proto_map: Dict[str, ProtocolInfo] = None

    def __init__(self, proto, factory):
        self.protocol = proto
        self.factory = factory
        self.store_map = {}

    def reset(self):
        for store in self.store_map:
            store.reset()

    def rent(self, type):
        if type is None:
            raise RuntimeError("Nil argument")

        store = self.store_map.get(type)
        if store is None:
            store = ObjectStore(lambda : PacketStore.create_packet(self.factory, type))
            self.store_map[type] = store

        return store.rent()

    def Return(self, pkt):
        store = self.store_map[pkt.type]
        #BayLog.info("Return packet %s", pkt)
        store.Return(pkt)

    def print_usage(self, indent):
        BayLog.info("%sPacketStore(%s) usage nTypes=%d", StringUtil.indent(indent), self.protocol, len(self.store_map))
        for type in self.store_map.keys():
            BayLog.info("%sType: %s", StringUtil.indent(indent+1), type)
            self.store_map[type].print_usage(indent+2)


    ######################################################
    # class methods
    ######################################################
    @classmethod
    def create_packet(cls, factory, type):
        if isinstance(factory, PacketFactory):
            return factory.create_packet(type)
        else:
            # lambda
            return factory(type)

    @classmethod
    def init(cls):
        if cls.proto_map is None:
            cls.proto_map = {}
            ga.GrandAgent.add_lifecycle_listener(PacketStore.AgentListener())


    @classmethod
    def get_store(cls, protocol, agent_id):
        return PacketStore.proto_map[protocol].stores[agent_id]


    @classmethod
    def register_protocol(cls, protocol, factory):
        if protocol not in PacketStore.proto_map.keys():
            PacketStore.proto_map[protocol] = PacketStore.ProtocolInfo(protocol, factory)

    @classmethod
    def get_stores(cls, agent_id):
        store_list = []
        for ifo in PacketStore.proto_map.values():
            store_list.append(ifo.stores[agent_id])
        return store_list