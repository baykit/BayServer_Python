import secrets
import traceback
import threading

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.common.transporter import Transporter
from bayserver_core.sink import Sink

from bayserver_docker_http3.qic_packet import QicPacket
from bayserver_docker_http3.qic_type import QicType


class QicTransporter(Transporter):
    """UDP transporter that owns a quiche server endpoint. Mirrors the Java
    QicTransporter: each inbound datagram is parsed, routed to an existing
    connection by DCID or used to create a new one (version negotiation /
    stateless retry / accept), and the per-connection outbound queue is
    drained via QicProtocolHandler.post_packets()."""

    CONN_ID_LEN = 16
    MAX_PKT_BUF = 1350

    # Shared across instances — same as Java's `static HashMap shipMap`.
    _ship_map_lock = threading.Lock()
    _ship_map = {}

    def __init__(self):
        super().__init__()
        self.multiplexer = None
        self.agent_id = -1
        self.rudder = None
        self.port_docker = None
        self.initialized = False
        self.server_name = None
        self.server_name_bytes = None
        self.local_addr = None
        # When the transporter has a single packet ready to post but no
        # ship to hold it (e.g. retry / version negotiation), park it here
        # and let post_packets drain it. Mirrors Java tmpPostPacket /
        # tmpPostAddress.
        self.tmp_post_packet = None
        self.tmp_post_address = None

    def __str__(self):
        return f"agt#{self.agent_id} udp"

    def init_udp(self, agent_id, rd, mpx, dkr):
        self.agent_id = agent_id
        self.rudder = rd
        self.multiplexer = mpx
        self.port_docker = dkr
        self.initialized = True
        self.server_name = BayServer.get_software_name() if hasattr(BayServer, "get_software_name") else "BayServer"
        self.server_name_bytes = self.server_name.encode("ascii", errors="replace")

        # croute's Address("0.0.0.0", <port>) used as the local recv side.
        from croute.quic import Address
        self.local_addr = Address("0.0.0.0", dkr.port())

    ######################################################
    # Implements Transporter
    ######################################################

    def init(self):
        pass

    def is_secure(self):
        return True

    def on_connected(self, rd):
        raise Sink()

    def on_read(self, rd, buf, adr):
        # croute Connection.recv wants the exact-size byte buffer for the
        # incoming UDP packet. Copy out of the rudder buffer here.
        packet_bytes = bytes(buf)

        BayLog.trace("%s notifyRead %d bytes", self, len(packet_bytes))

        from croute.error import CrouteError
        from croute.quic import Address, PacketHeader

        try:
            hdr = PacketHeader.parse(packet_bytes, len(packet_bytes), QicTransporter.CONN_ID_LEN)
        except CrouteError as e:
            BayLog.error("%s Header parse error: %s", self, e)
            return NextSocketAction.CONTINUE

        BayLog.debug("%s packet received type=%d version=%d", self, hdr.type, hdr.version)

        sender = Address(adr[0], adr[1]) if adr is not None else None

        sip = self._find_ship(hdr.dcid)
        if sip is None:
            if hdr.type != QicType.INITIAL:
                BayLog.warn("Client not registered (type=%d)", hdr.type)
            else:
                try:
                    sip = self._create_ship(hdr, sender)
                except Exception as e:
                    BayLog.error_e(e, traceback.format_stack(),
                                    "%s create ship failed", self)
                    return NextSocketAction.CONTINUE

        if sip is not None:
            # Feed the raw packet to the ship's protocol handler.
            try:
                sip.notify_read(packet_bytes, sender)
            except Exception as e:
                BayLog.error_e(e, traceback.format_stack())

        try:
            self.post_packets()
        except Exception as e:
            BayLog.error_e(e, traceback.format_stack(), "%s post_packets failed", self)

        self._cleanup_connections()
        return NextSocketAction.CONTINUE

    def on_error(self, rd, e, stk):
        BayLog.error_e(e, stk)

    def on_closed(self, rd):
        pass

    def req_connect(self, rd, adr):
        self.multiplexer.req_connect(rd, adr)

    def req_read(self, rd):
        self.multiplexer.req_read(rd)

    def req_write(self, rd, buf, adr, tag, listener):
        self.multiplexer.req_write(rd, buf, adr, tag, listener)

    def req_transfer(self, rd, file_rd, ofs, length, listener):
        raise Sink()

    def req_close(self, rd):
        self.multiplexer.req_close(rd)

    def check_timeout(self, rd, duration_sec):
        return False

    def get_read_buffer(self):
        return QicPacket.MAX_DATAGRAM_SIZE

    def print_usage(self, indent):
        pass

    def reset(self):
        pass

    ######################################################
    # Custom methods
    ######################################################

    def _create_ship(self, hdr, sender):
        from croute.error import CrouteError
        from croute.quic import Connection, Quiche

        if not Quiche.version_is_supported(hdr.version):
            self._negotiate_version(hdr, sender)
            return None

        if len(hdr.token) == 0:
            self._retry(hdr, sender)
            return None

        odcid = self._validate_token(sender, hdr.token)
        if odcid is None:
            raise IOError("Invalid address validation token")

        # Reuse the DCID we sent in the retry response as our SCID.
        src_con_id = hdr.dcid

        try:
            con = Connection.accept(src_con_id, odcid, self.local_addr, sender,
                                    self.port_docker.config)
        except CrouteError as e:
            raise IOError(f"Connection.accept failed: {e}")

        BayLog.info("%s New connection scid=%s odcid=%s", self,
                    src_con_id.hex(), odcid.hex())

        from bayserver_core.agent.grand_agent import GrandAgent
        from bayserver_core.common.inbound_ship import InboundShip
        from bayserver_docker_http3.qic_inbound_handler import QicInboundHandler
        from bayserver_docker_http3.qic_protocol_handler import QicProtocolHandler

        agt = GrandAgent.get(self.agent_id)
        ib_handler = QicInboundHandler()
        hnd = QicProtocolHandler(ib_handler, con, sender,
                                 self.local_addr, sender,
                                 self.port_docker.h3_config,
                                 agt.net_multiplexer)
        ib_handler.init(hnd)
        sip = InboundShip()
        sip.init_inbound(self.rudder, self.agent_id, self, self.port_docker, hnd)
        hnd.set_ship(sip)

        self._add_ship(src_con_id, sip)
        return sip

    def _find_ship(self, cid):
        with QicTransporter._ship_map_lock:
            return QicTransporter._ship_map.get(cid.hex())

    def _add_ship(self, cid, ship):
        with QicTransporter._ship_map_lock:
            QicTransporter._ship_map[cid.hex()] = ship

    def _mint_token(self, hdr, sender):
        """Stateless retry token: server_name + ip_bytes + odcid.
        Not cryptographically authenticated; same shape Java uses."""
        import ipaddress
        ip_bytes = ipaddress.ip_address(sender.ip).packed
        return self.server_name_bytes + ip_bytes + hdr.dcid

    def _validate_token(self, sender, tkn):
        if len(tkn) <= 8:
            return None
        if tkn[:len(self.server_name_bytes)] != self.server_name_bytes:
            return None
        import ipaddress
        ip_bytes = ipaddress.ip_address(sender.ip).packed
        rest = tkn[len(self.server_name_bytes):]
        if rest[:len(ip_bytes)] != ip_bytes:
            return None
        return rest[len(ip_bytes):]

    def _negotiate_version(self, hdr, sender):
        from croute.quic import Quiche
        from croute.error import CrouteError

        BayLog.info("%s Invalid quic version: %d. Start version negotiation",
                    self, hdr.version)
        out = bytearray(QicTransporter.MAX_PKT_BUF)
        try:
            n = Quiche.negotiate_version(hdr.scid, hdr.dcid, out)
        except CrouteError as e:
            raise IOError(f"Quiche: cannot create negotiate version packet: {e}")
        pkt = QicPacket()
        pkt.new_data_accessor().put_bytes(bytes(out[:n]), 0, n)
        self.tmp_post_packet = pkt
        self.tmp_post_address = sender

    def _retry(self, hdr, sender):
        from croute.quic import Quiche
        from croute.error import CrouteError

        new_scid = secrets.token_bytes(QicTransporter.CONN_ID_LEN)
        BayLog.info("%s Empty quic token. Retry scid=%s dcid=%s newid=%s",
                    self, hdr.scid.hex(), hdr.dcid.hex(), new_scid.hex())
        token = self._mint_token(hdr, sender)
        out = bytearray(QicTransporter.MAX_PKT_BUF)
        try:
            n = Quiche.retry(hdr.scid, hdr.dcid, new_scid, token, hdr.version, out)
        except CrouteError as e:
            raise IOError(f"Quiche: cannot create retry packet: {e}")
        pkt = QicPacket()
        pkt.new_data_accessor().put_bytes(bytes(out[:n]), 0, n)
        self.tmp_post_packet = pkt
        self.tmp_post_address = sender

    def post_packets(self):
        posted = False
        if self.tmp_post_packet is not None:
            buf = bytes(self.tmp_post_packet.buf[
                self.tmp_post_packet.header_len:
                self.tmp_post_packet.header_len + self.tmp_post_packet.data_len()])
            adr = (self.tmp_post_address.ip, self.tmp_post_address.port)
            self.multiplexer.req_write(self.rudder, buf, adr, self.tmp_post_packet, None)
            self.tmp_post_packet = None
            self.tmp_post_address = None
            posted = True
        with QicTransporter._ship_map_lock:
            ships = list(QicTransporter._ship_map.values())
        for s in ships:
            try:
                posted = s.protocol_handler.post_packets() or posted
            except Exception as e:
                BayLog.error_e(e, traceback.format_stack())
        return posted

    def _cleanup_connections(self):
        with QicTransporter._ship_map_lock:
            doomed = [k for k, s in QicTransporter._ship_map.items()
                      if s.protocol_handler.is_closed()]
            for k in doomed:
                BayLog.debug("%s cleaning up conn=%s", self, k)
                del QicTransporter._ship_map[k]
            if doomed:
                BayLog.debug("%s # of clients: %d", self, len(QicTransporter._ship_map))
