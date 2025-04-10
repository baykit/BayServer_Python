import socket
import threading
from abc import ABCMeta, abstractmethod

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.lifecycle_listener import LifecycleListener
from bayserver_core.bay_log import BayLog
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.config_exception import ConfigException

from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.docker.warp import Warp
from bayserver_core.common.warp_ship_store import WarpShipStore
from bayserver_core.common.warp_data_listener import WarpDataListener

from bayserver_core.http_exception import HttpException
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.ship.ship import Ship
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus


class WarpBase(ClubBase, Warp, metaclass=ABCMeta):

    class AgentListener(LifecycleListener):

        def __init__(self, dkr):
            self.warp_docker = dkr

        def add(self, agt_id: int):
            self.warp_docker.stores[agt_id] = WarpShipStore(self.warp_docker.max_ships)

        def remove(self, agt_id: int):
            del self.warp_docker.stores[agt_id]


    class WarpShipHolder:

        def __init__(self, owner_id, ship_id, ship):
            self.owner_id = owner_id
            self.ship_id = ship_id
            self.ship = ship

    ######################################################
    # Abstract methods
    ######################################################

    @abstractmethod
    def secure(self):
        pass

    @abstractmethod
    def protocol(self):
        pass

    @abstractmethod
    def new_transporter(self, agt: GrandAgent, rd: SocketRudder, sip: Ship):
        pass


    def __init__(self):
        super().__init__()
        self.scheme = None
        self._host = None
        self._port = -1
        self._warp_base = None
        self.max_ships = -1
        self.cur_ships = 0
        self.host_addr = None
        self.tour_list = []
        self._timeout_sec = -1  # -1 means "Use harbor.socketTimeoutSec"

        # Agent ID => WarpShipStore
        self.stores = {}

        self.lock = threading.RLock()

    ######################################################
    # Implements DockerBase
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        if self._warp_base is None:
            self._warp_base = "/"

        if self._host and self._host.startswith(":unix:"):
            self.host_addr = [None, None, None, None, None]
            self.host_addr[0] = socket.AF_UNIX
            self.host_addr[4] = self._host[6:]
            self._port = -1
        else:
            if self._port <= 0:
                self._port = 80
            addrs = socket.getaddrinfo(self._host, self._port)
            inet4_addr = None
            inet6_addr = None
            if addrs:
                for addr_info in addrs:
                    if addr_info[1] == socket.SOCK_STREAM or addr_info[1] == 0:
                        if addr_info[0] == socket.AF_INET:
                            inet4_addr = addr_info
                        elif addr_info[0] == socket.AF_INET6:
                            inet6_addr = addr_info

            if inet4_addr:
                self.host_addr = inet4_addr
            elif inet6_addr:
                self.host_addr = inet6_addr
            else:
                raise ConfigException(elm.file_name, elm.line_no, "Host not found: %s", self._host)


        GrandAgent.add_lifecycle_listener(WarpBase.AgentListener(self))

        BayLog.info("WarpDocker[%s] host=%s port=%d ipv6=%s", self._warp_base, self._host, self._port, self.host_addr[0] == socket.AF_INET6)

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "destcity":
            self._host = kv.value

        elif key == "destport":
            self._port = int(kv.value)

        elif key == "desttown":
            self._warp_base = kv.value
            if not self._warp_base.endswith("/"):
                self._warp_base += "/"

        elif key == "maxships":
            self.max_ships = int(kv.value)

        elif key == "timeout":
            self._timeout_sec = int(kv.value)

        else:
            return super().init_key_val(kv)

        return True

    ######################################################
    # Implements Club
    ######################################################

    def arrive(self, tour: Tour):
        agt = GrandAgent.get(tour.ship.agent_id)
        sto = self.get_ship_store(agt.agent_id)

        wsip = sto.rent()
        if wsip is None:
            BayLog.warn("%s Busy!", self)
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, "WarpDocker busy")

        try:
            BayLog.trace("%s got from store", wsip)
            need_connect = False

            tp = None
            if not wsip.initialized:
                if self.host_addr[0] == socket.AF_UNIX:
                    skt = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
                else:
                    skt = socket.socket(self.host_addr[0], socket.SOCK_STREAM, 0)
                rd = SocketRudder(skt)
                rd.set_non_blocking()

                tp = self.new_transporter(agt, rd, wsip)
                proto_hnd = ProtocolHandlerStore.get_store(self.protocol(), False, agt.agent_id).rent()
                wsip.init_warp(rd, agt.agent_id, tp, self, proto_hnd)

                BayLog.debug("%s init warp ship", wsip)
                BayLog.debug("%s Connect to %s:%d skt=%s", wsip, self._host, self._port, skt)

                need_connect = True

            with self.lock:
                self.tour_list.append(tour)

            wsip.start_warp_tour(tour)

            if need_connect:
                agt.net_multiplexer.add_rudder_state(wsip.rudder, RudderState(wsip.rudder, tp))
                agt.net_multiplexer.get_transporter(wsip.rudder).req_connect(wsip.rudder, self.host_addr[4])

        except HttpException as e:
            raise e

    ######################################################
    # Implements Warp
    ######################################################

    def host(self) -> str:
        return self._host

    def port(self) -> int:
        return self._port

    def warp_base(self) -> str:
        return self._warp_base

    def timeout_sec(self) -> int:
        return self._timeout_sec

    def keep(self, wsip: Ship) -> None:
        BayLog.debug("%s keepShip: %s", self, wsip)
        self.get_ship_store(wsip.agent_id).keep(wsip)

    def on_end_ship(self, warp_ship: Ship) -> None:
        BayLog.debug("%s Return protocol handler: ", warp_ship)
        self.get_protocol_handler_store(warp_ship.agent_id).Return(warp_ship.protocol_handler)
        BayLog.debug("%s return ship: %s", self, warp_ship)
        self.get_ship_store(warp_ship.agent_id).Return(warp_ship)
        pass

    ######################################################
    # Other methods
    ######################################################

    def return_ship(self, wsip):
        BayLog.debug("%s return ship: %s", self, wsip)
        self.get_ship_store(wsip.agent.agent_id).Return(wsip)

    def return_protocol_handler(self, agt, phnd):
        BayLog.debug("%s Return protocol handler: ", phnd)
        self.get_protocol_handler_store(agt.agent_id).Return(phnd)

    def get_ship_store(self, agent_id):
        return self.stores[agent_id]

    ######################################################
    # private methods
    ######################################################
    def get_protocol_handler_store(self, agt_id):
        return ProtocolHandlerStore.get_store(self.protocol(), False, agt_id)
