import os

from aioquic.buffer import Buffer
from aioquic.quic import packet
from aioquic.quic.connection import QuicConnection
from aioquic.quic.packet import QuicProtocolVersion
from aioquic.quic.retry import QuicRetryTokenHandler

from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.transporter.data_listener import DataListener
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.docker.base.inbound_ship import InboundShip
from bayserver_core.util.exception_util import ExceptionUtil

from bayserver_docker_http3.qic_packet import QicPacket
from bayserver_docker_http3.qic_type import QicType
from bayserver_docker_http3.qic_protocol_handler import QicProtocolHandler


class UdpInboundDataListener(DataListener):

    def __init__(self):
        self.postman = None
        self.agent = None
        self.socket = None
        self.port_dkr = None
        self.initialized = None
        self.ship = None
        self.handlers = {}
        self.tmp_post_packet = None
        self.tmp_post_address = None
        self.retry_token_handler = QuicRetryTokenHandler()


    def __str__(self):
        return f"{self.agent} udp"

    def init_udp(self, skt, agt, postman, port_dkr):
        self.socket = skt
        self.agent = agt
        self.postman = postman
        self.port_dkr = port_dkr
        self.initialized = True

    ######################################################
    # Implements DataListener
    ######################################################

    def notify_connect(self):
        raise Sink()

    def notify_read(self, buf, adr):
        #BayLog.debug("%s notify_read", self)

        try:
            hdr = packet.pull_quic_header(buf=Buffer(data=buf), host_cid_length=self.port_dkr.config.connection_id_length)
        except ValueError as e:
            BayLog.warn_e(e, "%s Cannot parse header: %s", self, ExceptionUtil.message(e))
            return NextSocketAction.CONTINUE

        BayLog.debug("%s packet received :len=%d ver=%s type=%s scid=%s dcid=%s tkn=%s",
                     self, len(buf), hdr.version, QicType.packet_type_name(hdr.packet_type), hdr.source_cid.hex(), hdr.destination_cid.hex(),
                     hdr.token.hex())

        con_id = hdr.destination_cid

        # find handler
        hnd = self.get_handler(hdr)
        #BayLog.debug("%s cid=%s hnd=%s", self, con_id.hex(), hnd)
        #BayLog.debug("%s con_id=%s hnd=%s", self, con_id, hnd)
        if hnd is None:
            BayLog.debug("%s handler not found", self)
            if hdr.packet_type != packet.PACKET_TYPE_INITIAL:
                BayLog.warn("handler not registered")
                new_con_id = os.urandom(8)
                self.retry(new_con_id, hdr, adr)
            else:
                hnd = self.create_handler(con_id, hdr, adr)

        if hnd:
            hnd.bytes_received(buf)

        posted = self.post_packets()

        if posted:
            return NextSocketAction.WRITE
        else:
            return NextSocketAction.CONTINUE


    def notify_eof(self):
        return NextSocketAction.CONTINUE

    def notify_handshake_done(self, protocol):
        raise Sink()

    def notify_protocol_error(self, err):
        BayLog.error_e(err)
        return False

    def notify_close(self):
        pass

    def check_timeout(self, duration_sec):
        BayLog.debug("%s Check H3Conn timeout: %s", self, self.handlers)
        remove_list = []
        for key, handler in self.handlers.items():
            BayLog.debug("%s Check H3Conn handler: key = %s", self, key)
            if handler.is_timed_out():
                remove_list.append(key)
        for key in remove_list:
            BayLog.debug("%s Remove key: %s", self, key)
            del self.handlers[key]
        return False

    ######################################################
    # Custom methods
    ######################################################

    def get_handler(self, hdr):
        return self.find_handler(hdr.destination_cid)

    def find_handler(self, id):
        #BayLog.debug("find handler: %s", id.hex())
        return self.handlers.get(id)

    def add_handler(self, id, hnd):
        #BayLog.debug("add handler: %s", id.hex())
        self.handlers[id] = hnd

    def version_is_supported(self, ver):
        return ver and ver in self.port_dkr.config.supported_versions

    def negotiate_version(self, hdr, adr):
        BayLog.info("%s start negotiation", self)
        pkt = QicPacket()
        pkt.buf = packet.encode_quic_version_negotiation(
            source_cid = hdr.destination_cid,
            destination_cid = hdr.source_cid,
            supported_versions = self.port_dkr.config.supported_versions,
        )
        pkt.buf_len = len(pkt.buf)
        self.tmp_post_packet = pkt
        self.tmp_post_address = adr

    def validate_token(self, adr, tkn):
        if len(tkn) <= 8:
            return None

        if self.port_dkr.server_name != tkn[0:len(self.port_dkr.server_name)]:
            return None

        #address = adr.getAddress();
        #if (!Arrays.equals(addr, Arrays.copyOfRange(token, serverNameBytes.length, addr.length + serverNameBytes.length)))
        #    return null;
        return tkn[len(self.port_dkr.server_name) + len(adr):len(tkn)]

    def retry(self, new_scid, hdr, adr):
        pkt = QicPacket()

        tkn = self.retry_token_handler.create_token(adr, hdr.destination_cid, new_scid)
        BayLog.info("%s retry(new_scid=%s scid=%s dcid=%s tkn=%s)", self, new_scid.hex(), hdr.source_cid.hex(), hdr.destination_cid.hex(), tkn.hex())
        pkt.buf = packet.encode_quic_retry(
            version = QuicProtocolVersion.VERSION_1,
            source_cid = new_scid,
            destination_cid = hdr.source_cid,
            original_destination_cid = hdr.destination_cid,
            retry_token = tkn
        )
        pkt.buf_len = len(pkt.buf)
        self.tmp_post_packet = pkt
        self.tmp_post_address = adr

    def create_handler(self, con_id, hdr, adr):
        #BayLog.debug("create handler: %s", con_id.hex())
        # version negotiation
        if not self.version_is_supported(hdr.version):
            self.negotiate_version(hdr, adr)
            return None

        if not hdr.token:
            new_con_id = os.urandom(8)
            self.retry(new_con_id, hdr, adr)
            return None

        # Validate token
        try:
            (odcid, scid) = self.retry_token_handler.validate_token(adr, hdr.token)
        except ValueError as e:
            BayLog.error_e(e)
            raise ProtocolException("Invalid address validation token")

        # create new connection
        con = QuicConnection(
            configuration=self.port_dkr.config,
            original_destination_connection_id=odcid,
            retry_source_connection_id=scid,
            session_ticket_fetcher=self.port_dkr.session_ticket_fetcher,
            session_ticket_handler=self.port_dkr.session_ticket_handler,
        )

        BayLog.debug("%s create connection: scid=%s hcid=%s", self, scid.hex(), con.host_cid.hex())
        hnd = QicProtocolHandler(con, adr, None, self.postman)
        sip = InboundShip()
        sip.init_inbound(self.socket, self.agent, self.postman, self.port_dkr, hnd)
        hnd.ship = sip

        self.add_handler(con_id, hnd)
        self.add_handler(con.host_cid, hnd)

        return hnd


    def post_packets(self):

        posted = False

        if self.tmp_post_packet:
            self.postman.post(self.tmp_post_packet.buf, self.tmp_post_address, self.tmp_post_packet, None)
            self.tmp_post_packet = None
            self.tmp_post_address = None
            posted = True

        # Check packets held in protocol handlers
        for hnd in self.handlers.values():
            posted |= hnd.post_packets()

        return posted


