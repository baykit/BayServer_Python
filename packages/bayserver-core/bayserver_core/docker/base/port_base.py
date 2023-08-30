from abc import ABCMeta, abstractmethod

from bayserver_core.config_exception import ConfigException
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.bay_log import BayLog
from bayserver_core.agent.transporter.plain_transporter import PlainTransporter
from bayserver_core.docker.port import Port
from bayserver_core.docker.secure import Secure
from bayserver_core.docker.city import City
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.base.inbound_data_listener import InboundDataListener
from bayserver_core.docker.permission import Permission
from bayserver_core.docker.base.inbound_ship_store import InboundShipStore
from bayserver_core.protocol.protocol_handler_store import ProtocolHandlerStore

from bayserver_core.util.io_util import IOUtil
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.cities import Cities

class PortBase(DockerBase, Port, metaclass=ABCMeta):

    def __init__(self):
        super().__init__()
        self.permission_list = []
        self.timeout_sec = -1
        self.host = None
        self.port = -1
        self.anchored = True
        self.additional_headers = []
        self.socket_path = None
        self.secure_docker = None
        self.cities = Cities()

    def __str__(self):
        return super().__str__() + "[" + str(self.port) + "]"

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
            self.port = -1
            self.socket_path = port_name[6:]
            self.host = elm.arg
        else:
            # TCP or UDP port
            if port_name.startswith(":tcp:"):
                # tcp server socket
                self.anchored = True
                host_port = elm.arg[5:]
            elif port_name.startswith(":udp:"):
                # udp server socket
                self.anchored = False
                host_port = elm.arg[5:]
            else:
                # default: tcp server socket
                self.anchored = True
                host_port = elm.arg

            try:
                idx = host_port.find(':')
                if idx == -1:
                    self.host = None
                    self.port = int(host_port)
                else:
                    self.host = host_port[0:idx]
                    self.port = int(host_port[idx + 1:])
            except Exception as e:
                raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_INVALID_PORT_NAME, elm.name))

        if self.anchored:
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
            self.cities.add(dkr)
        elif isinstance(dkr, Secure):
            self.secure_docker = dkr
        else:
            return super().init_docker(dkr)

        return True

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "timeout":
            self.timeout_sec = int(kv.value)

        elif key == "addheader":
            idx = kv.value.find(':')
            if idx == -1:
                raise ConfigException(kv.file_name, kv.line_no, BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, kv.value))
            name = kv.value[0:idx].strip()
            value = kv.value[idx+1:].strip()
            self.additional_headers.append([name, value])

        else:
            return super().init_key_val(kv)
        return True

    ######################################################
    # implements Port
    ######################################################
    def address(self, null=None):
        if self.socket_path:
            #  Unix domain socket
            return self.socket_path
        elif self.host is None:
            return ("0.0.0.0", self.port)
        else:
            return (self.host, self.port)

    def secure(self):
        return self.secure_docker is not None

    def check_admitted(self, skt):
        for perm_dkr in self.permission_list:
            perm_dkr.socket_admitted(skt)

    def find_city(self, name):
        return self.cities.find_city(name)

    def new_transporter(self, agt, skt):
        sip = PortBase.get_ship_store(agt).rent()
        if self.secure():
            tp = self.secure_docker.create_transporter(IOUtil.get_sock_recv_buf_size(skt))
            skt = self.secure_docker.sslctx.wrap_socket(skt, server_side=True, do_handshake_on_connect=False)
        else:
            tp = PlainTransporter(True, IOUtil.get_sock_recv_buf_size(skt))

        proto_hnd = PortBase.get_protocol_handler_store(self.protocol(), agt).rent()
        sip.init_inbound(skt, agt, tp, self, proto_hnd)
        tp.init(agt.non_blocking_handler, skt, InboundDataListener(sip))
        return tp



    def return_protocol_handler(self, agt, proto_hnd):
        BayLog.debug("%s Return protocol handler: ", proto_hnd)
        self.get_protocol_handler_store(proto_hnd.protocol(), agt).Return(proto_hnd)

    def return_ship(self, sip):
        BayLog.debug("%s end (return ships)", sip)
        self.get_ship_store(sip.agent).Return(sip)

    @classmethod
    def get_ship_store(cls, agt):
        return InboundShipStore.get_store(agt.agent_id)

    @classmethod
    def get_protocol_handler_store(cls, proto, agt):
        return ProtocolHandlerStore.get_store(proto, True, agt.agent_id)
