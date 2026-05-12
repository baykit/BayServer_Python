from typing import Dict

from bayserver_core.agent import grand_agent as ga
from bayserver_core.agent.lifecycle_listener import LifecycleListener
from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.command_factory import CommandFactory
from bayserver_core.util.object_store import ObjectStore
from bayserver_core.util.reusable import Reusable


class CommandStore(Reusable):
    """Per-agent pool of Command objects, keyed by command type. Mirrors
    PacketStore but for Commands: each (protocol, type) gets an
    ObjectStore so the hot path can rent/return instead of allocating a
    fresh Command per inbound or outbound frame.
    """

    class AgentListener(LifecycleListener):

        def add(self, agt_id: int):
            for ifo in CommandStore.proto_map.values():
                ifo.add_agent(agt_id)

        def remove(self, agt_id: int):
            for ifo in CommandStore.proto_map.values():
                ifo.remove_agent(agt_id)

    class ProtocolInfo:
        protocol: str
        stores: Dict[int, "CommandStore"]
        command_factory: CommandFactory

        def __init__(self, proto, cmd_factory):
            self.protocol = proto
            self.stores = {}
            self.command_factory = cmd_factory

        def add_agent(self, agt_id: int):
            self.stores[agt_id] = CommandStore(self.protocol, self.command_factory)

        def remove_agent(self, agt_id: int):
            BayLog.debug("CommandStore[%s]: removing agent %d",
                         self.protocol, agt_id)
            self.stores.pop(agt_id, None)

    proto_map: Dict[str, ProtocolInfo] = None

    def __init__(self, proto, factory):
        self.protocol = proto
        self.factory = factory
        # type id -> ObjectStore[Command]. Sized lazily on first rent for
        # a given type; protocols use small dense type-id ranges so a
        # dict is fine.
        self.store_map = {}

    def reset(self):
        for store in self.store_map.values():
            store.reset()

    def rent(self, type):
        store = self.store_map.get(type)
        if store is None:
            factory = self.factory
            store = ObjectStore(lambda: factory.create_command(type))
            self.store_map[type] = store
        return store.rent()

    def Return(self, cmd):
        store = self.store_map.get(cmd.type)
        if store is not None:
            store.Return(cmd)

    def print_usage(self, indent):
        BayLog.info("%sCommandStore(%s) usage nTypes=%d",
                    " " * (indent * 2), self.protocol, len(self.store_map))
        for typ, store in self.store_map.items():
            BayLog.info("%sType: %d", " " * ((indent + 1) * 2), typ)
            store.print_usage(indent + 2)

    @classmethod
    def init(cls):
        if cls.proto_map is None:
            cls.proto_map = {}
        ga.GrandAgent.add_lifecycle_listener(CommandStore.AgentListener())

    @classmethod
    def get_store(cls, protocol, agt_id):
        return cls.proto_map[protocol].stores[agt_id]

    @classmethod
    def register_protocol(cls, protocol, cmd_factory):
        if cls.proto_map is None:
            cls.proto_map = {}
        if protocol not in cls.proto_map:
            cls.proto_map[protocol] = CommandStore.ProtocolInfo(
                protocol, cmd_factory)

    @classmethod
    def get_stores(cls, agt_id):
        return [ifo.stores.get(agt_id) for ifo in cls.proto_map.values()
                if ifo.stores.get(agt_id) is not None]
