from abc import ABCMeta, abstractmethod
from typing import List

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.config_exception import ConfigException
from bayserver_core.bay_message import BayMessage
from bayserver_core.protocol.protocol_handler import ProtocolHandler
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.symbol import Symbol
from bayserver_core.bay_log import BayLog
from bayserver_core.docker.port import Port
from bayserver_core.docker.secure import Secure
from bayserver_core.docker.city import City
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.permission import Permission
from bayserver_core.common.inbound_ship_store import InboundShipStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore

from bayserver_core.util.io_util import IOUtil
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.cities import Cities

class PortBase(DockerBase, Port, metaclass=ABCMeta):

    permission_list: List[Permission]
    _host: str
    _port: int
    _anchored: bool
    _additional_headers: List[List[str]]
    _socket_path: str
    _timeout_sec: int
    _secure_docker: Secure
    _cities: Cities

    def __init__(self):
        super().__init__()
        self.permission_list = []
        self._timeout_sec = -1
        self._host = None
        self._port = -1
        self._anchored = True
        self._additional_headers = []
        self._socket_path = None
        self._secure_docker = None
        self._cities = Cities()

    def __str__(self):
        return super().__str__() + "[" + str(self._port) + "]"

    ######################################################
    # Abstract methods
    ######################################################
    @abstractmethod
    def support_anchored(self):
        pass

    @abstractmethod
    def support_unanchored(self):
        pass

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        if StringUtil.is_empty(elm.arg):
            raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_INVALID_PORT_NAME, elm.name))

        super().init(elm, parent)

        port_name = elm.arg.lower()
        if port_name.startswith(":unix:"):
            # Unix domain socket
            self._port = -1
            self._socket_path = port_name[6:]
            self._host = elm.arg
        else:
            # TCP or UDP port
            if port_name.startswith(":tcp:"):
                # tcp server socket
                self._anchored = True
                host_port = elm.arg[5:]
            elif port_name.startswith(":udp:"):
                # udp server socket
                self._anchored = False
                host_port = elm.arg[5:]
            else:
                # default: tcp server socket
                self._anchored = True
                host_port = elm.arg

            try:
                idx = host_port.find(':')
                if idx == -1:
                    self._host = None
                    self._port = int(host_port)
                else:
                    self._host = host_port[0:idx]
                    self._port = int(host_port[idx + 1:])
            except Exception as e:
                raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_INVALID_PORT_NAME, elm.name))

        if self._anchored:
            if not self.support_anchored():
                raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_TCP_NOT_SUPPORTED))
        else:
            if not self.support_unanchored():
                raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_UDP_NOT_SUPPORTED))

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_docker(self, dkr):
        if isinstance(dkr, Permission):
            self.permission_list.append(dkr)
        elif isinstance(dkr, City):
            self._cities.add(dkr)
        elif isinstance(dkr, Secure):
            self._secure_docker = dkr
        else:
            return super().init_docker(dkr)

        return True

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "timeout":
            self._timeout_sec = int(kv.value)

        elif key == "addheader":
            idx = kv.value.find(':')
            if idx == -1:
                raise ConfigException(kv.file_name, kv.line_no, BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))
            name = kv.value[0:idx].strip()
            value = kv.value[idx+1:].strip()
            self._additional_headers.append([name, value])

        else:
            return super().init_key_val(kv)
        return True

    ######################################################
    # implements Port
    ######################################################

    def host(self) -> str:
        return self._host

    def port(self) -> int:
        return self._port

    def socket_path(self) -> str:
        return self._socket_path

    def address(self, null=None):
        if self._socket_path:
            #  Unix domain socket
            return self._socket_path
        elif self._host is None:
            return ("0.0.0.0", self._port)
        else:
            return (self._host, self._port)

    def anchored(self) -> bool:
        return self._anchored

    def timeout_sec(self) -> int:
        return self._timeout_sec

    def secure(self):
        return self._secure_docker is not None

    def additional_headers(self) -> List[List[str]]:
        return self._additional_headers

    def cities(self) -> List[City]:
        return self._cities.cities()

    def find_city(self, name):
        return self._cities.find_city(name)

    def on_connected(self, agt_id: int, rd: Rudder) -> None:

        self.check_admitted(rd)

        sip = PortBase.get_ship_store(agt_id).rent()
        agt = GrandAgent.get(agt_id)

        if self.anchored() and self.secure():
            tp = (
                self._secure_docker.new_transporter(
                    agt_id,
                    sip,
                    IOUtil.get_sock_recv_buf_size(rd.key())
            ))
            ssl_soket = self._secure_docker.sslctx.wrap_socket(rd.key(), server_side=True, do_handshake_on_connect=False)
            rd = SocketRudder(ssl_soket)
            if agt.net_multiplexer.is_non_blocking():
                rd.set_non_blocking()

        else:
            size = IOUtil.get_sock_recv_buf_size(rd.key())

            tp = PlainTransporter(
                agt.net_multiplexer,
                sip,
                True,
                size,
                False)

        proto_hnd = PortBase.get_protocol_handler_store(self.protocol(), agt_id).rent()
        sip.init_inbound(rd, agt_id, tp, self, proto_hnd)

        st = RudderState(rd, tp)
        agt.net_multiplexer.add_rudder_state(rd, st)
        agt.net_multiplexer.req_read(rd)



    def return_protocol_handler(self, agt_id: int, proto_hnd: ProtocolHandler) -> None:
        BayLog.debug("%s Return protocol handler: ", proto_hnd)
        self.get_protocol_handler_store(proto_hnd.protocol(), agt_id).Return(proto_hnd)

    def return_ship(self, sip):
        BayLog.debug("%s end (return ships)", sip)
        self.get_ship_store(sip.agent_id).Return(sip)

    ######################################################
    # private methods
    ######################################################

    def check_admitted(self, rd: SocketRudder) -> None:
        for p in self.permission_list:
            p.socket_admitted(rd)


    ######################################################
    # class methods
    ######################################################

    @classmethod
    def get_ship_store(cls, agt_id: int):
        return InboundShipStore.get_store(agt_id)

    @classmethod
    def get_protocol_handler_store(cls, proto, agt_id: int):
        return ProtocolHandlerStore.get_store(proto, True, agt_id)
