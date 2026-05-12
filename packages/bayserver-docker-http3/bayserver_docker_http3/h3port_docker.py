import os

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.config_exception import ConfigException
from bayserver_core.docker.base.port_base import PortBase
from bayserver_core.symbol import Symbol

from bayserver_docker_http3.h3_docker import H3Docker
from bayserver_docker_http3.qic_packet import QicPacket


# Imported lazily inside init() so an environment without croute /
# libquiche does not fail to load the module list at startup.


class H3PortDocker(PortBase, H3Docker):
    APP_PROTOCOLS = ["h3", "h3-29", "h3-28", "h3-27"]

    def __init__(self):
        PortBase.__init__(self)
        self.config = None
        # croute objects are kept on the docker; QicTransporter reads them
        # back via the port_docker reference.
        self.h3_config = None

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        if self._secure_docker is None:
            raise ConfigException(elm.file_name, elm.line_no,
                                  "H3 port requires [secure] sub-docker")
        cert = getattr(self._secure_docker, "cert_file", None)
        key = getattr(self._secure_docker, "key_file", None)
        if not cert or not os.path.isfile(cert):
            raise ConfigException(elm.file_name, elm.line_no,
                                  BayMessage.get(Symbol.CFG_SSL_CERT_FILE_NOT_SPECIFIED))
        if not key or not os.path.isfile(key):
            raise ConfigException(elm.file_name, elm.line_no,
                                  BayMessage.get(Symbol.CFG_SSL_KEY_FILE_NOT_SPECIFIED))

        from croute.quic import Config as QConfig
        from croute.h3 import Config as H3Config

        # build the ALPN bytes (length-prefixed protocol names) per RFC 7301
        alpn = bytearray()
        for proto in H3PortDocker.APP_PROTOCOLS:
            b = proto.encode("ascii")
            alpn.append(len(b))
            alpn.extend(b)

        self.config = QConfig.server(cert, key)
        self.config.set_application_protos(bytes(alpn))
        self.config.set_max_idle_timeout(5_000)
        self.config.set_max_recv_udp_payload_size(QicPacket.MAX_DATAGRAM_SIZE)
        self.config.set_max_send_udp_payload_size(QicPacket.MAX_DATAGRAM_SIZE)
        self.config.set_initial_max_data(10_000_000)
        self.config.set_initial_max_stream_data_bidi_local(1_000_000)
        self.config.set_initial_max_stream_data_bidi_remote(1_000_000)
        self.config.set_initial_max_stream_data_uni(1_000_000)
        self.config.set_initial_max_streams_bidi(4)
        self.config.set_initial_max_streams_uni(4)
        self.config.set_disable_active_migration(True)
        self.config.enable_early_data()

        self.h3_config = H3Config()
        BayLog.debug("H3 port initialized")

    ######################################################
    # Implements Port
    ######################################################

    def protocol(self):
        return H3Docker.PROTO_NAME

    def self_listen(self):
        return False

    def listen(self):
        pass

    ######################################################
    # Implements PortBase
    ######################################################

    def support_anchored(self):
        return False

    def support_unanchored(self):
        return True

    def on_connected(self, agent_id, rd):
        # Lazy import to avoid pulling croute into module-load order for
        # users that never enable H3.
        from bayserver_docker_http3.qic_transporter import QicTransporter
        from bayserver_core.agent.grand_agent import GrandAgent

        agt = GrandAgent.get(agent_id)
        tp = QicTransporter()
        tp.init_udp(agent_id, rd, agt.net_multiplexer, self)

        # Reuse existing rudder state if any, otherwise create one.
        st = agt.net_multiplexer.get_rudder_state(rd)
        if st is None:
            from bayserver_core.common.rudder_state import RudderState
            st = RudderState(rd, tp)
            agt.net_multiplexer.add_rudder_state(rd, st)
        else:
            st.transporter = tp
        agt.net_multiplexer.req_read(rd)
