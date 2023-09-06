import socket
import threading
from abc import ABCMeta, abstractmethod

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.bay_log import BayLog
from bayserver_core.config_exception import ConfigException

from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.docker.warp.warp_ship_store import WarpShipStore
from bayserver_core.docker.warp.warp_data_listener import WarpDataListener

from bayserver_core.http_exception import HttpException
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore
from bayserver_core.util.http_status import HttpStatus


class WarpDocker(ClubBase, metaclass=ABCMeta):

    class AgentListener(GrandAgent.GrandAgentLifecycleListener):

        def __init__(self, dkr):
            self.warp_docker = dkr

        def add(self, agt):
            self.warp_docker.stores[agt.agent_id] = WarpShipStore(self.warp_docker.max_ships);

        def remove(self, agt):
            del self.warp_docker.stores[agt.agent_id]


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
    def new_transporter(self, agent, ch):
        pass


    def __init__(self):
        super().__init__()
        self.scheme = None
        self.host = None
        self.port = -1
        self.warp_base = None
        self.max_ships = -1
        self.cur_ships = 0
        self.host_addr = None
        self.tour_list = []
        self.timeout_sec = -1  # -1 means "Use harbor.socketTimeoutSec"

        # Agent ID => WarpShipStore
        self.stores = {}

        self.lock = threading.RLock()

    ######################################################
    # Implements DockerBase
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        if self.warp_base is None:
            self.warp_base = "/"

        if self.host and self.host.startswith(":unix:"):
            self.host_addr = [None, None, None, None, None]
            self.host_addr[0] = socket.AF_UNIX
            self.host_addr[4] = self.host[6:]
            self.port = -1
        else:
            if self.port <= 0:
                self.port = 80
            addrs = socket.getaddrinfo(self.host, self.port)
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
                raise ConfigException(elm.file_name, elm.line_no, "Host not found: %s", self.host)


        GrandAgent.add_lifecycle_listener(WarpDocker.AgentListener(self))

        BayLog.info("WarpDocker[%s] host=%s port=%d ipv6=%s", self.warp_base, self.host, self.port, self.host_addr[0] == socket.AF_INET6)

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "destcity":
            self.host = kv.value

        elif key == "destport":
            self.port = int(kv.value)

        elif key == "desttown":
            self.warp_base = kv.value
            if not self.warp_base.endswith("/"):
                self.warp_base += "/"

        elif key == "maxships":
            self.max_ships = int(kv.value)

        elif key == "timeout":
            self.timeout_sec = int(kv.value)

        else:
            return super().init_key_val(kv)

        return True

    ######################################################
    # Implements Club
    ######################################################

    def arrive(self, tour):
        agt = tour.ship.agent
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
                skt.setblocking(False)

                tp = self.new_transporter(agt, skt)
                proto_hnd = ProtocolHandlerStore.get_store(self.protocol(), False, agt.agent_id).rent()
                wsip.init_warp(skt, agt, tp, self, proto_hnd)
                tp.init(agt.non_blocking_handler, skt, WarpDataListener(wsip))
                BayLog.debug("%s init warp ship", wsip)
                BayLog.debug("%s Connect to %s:%d skt=%s", wsip, self.host, self.port, skt)

                need_connect = True

            with self.lock:
                self.tour_list.append(tour)

            wsip.start_warp_tour(tour)

            if need_connect:
                agt.non_blocking_handler.add_channel_listener(wsip.socket, tp)
                agt.non_blocking_handler.ask_to_connect(wsip.socket, self.host_addr[4])

        except HttpException as e:
            raise e

    ######################################################
    # Implements WarpDocker
    ######################################################
    def keep_ship(self, wsip):
        BayLog.debug("%s keepShip: %s", self, wsip)
        self.get_ship_store(wsip.agent.agent_id).keep(wsip)

    def return_ship(self, wsip):
        BayLog.debug("%s return ship: %s", self, wsip)
        self.get_ship_store(wsip.agent.agent_id).Return(wsip)

    def return_protocol_handler(self, agt, phnd):
        BayLog.debug("%s Return protocol handler: ", phnd)
        self.get_protocol_handler_store(agt.agent_id).Return(phnd)


    ######################################################
    # Other methods
    ######################################################
    def get_ship_store(self, agent_id):
        return self.stores[agent_id]

    ######################################################
    # private methods
    ######################################################
    def get_protocol_handler_store(self, agt_id):
        return ProtocolHandlerStore.get_store(self.protocol(), False, agt_id)
