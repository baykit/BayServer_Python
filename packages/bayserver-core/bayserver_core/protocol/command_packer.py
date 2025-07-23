from typing import Any

from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.command import Command
from bayserver_core.protocol.packet_packer import PacketPacker
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.ship.ship import Ship
from bayserver_core.util.reusable import Reusable
from bayserver_core.util.data_consume_listener import DataConsumeListener

class CommandPacker(Reusable):

    pkt_packer: PacketPacker
    pkt_srtore: PacketStore

    def __init__(self, pkt_packer: PacketPacker, store: PacketStore):
        self.pkt_packer = pkt_packer
        self.pkt_store = store


    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        pass


    ######################################################
    # Other methods
    ######################################################

    def post(self, sip: Ship, cmd: Command, lis: DataConsumeListener=None, adr: Any=None):
        pkt = self.pkt_store.rent(cmd.type)

        try:
            cmd.pack(pkt)

            def done() -> None:
                self.pkt_store.Return(pkt)
                if lis is not None:
                    lis()

            self.pkt_packer.post(sip, adr, pkt, done)
        except IOError as e:
            self.pkt_store.Return(pkt)
            raise e
00