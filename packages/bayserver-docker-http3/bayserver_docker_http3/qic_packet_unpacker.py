
import os
from typing import Dict

from aioquic.buffer import Buffer
from aioquic.quic import packet
from aioquic.quic.connection import QuicConnection
from aioquic.quic.packet import QuicProtocolVersion
from aioquic.quic.retry import QuicRetryTokenHandler

from bayserver_core.agent import grand_agent as ga
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.packet_store import PacketStore
from bayserver_core.protocol.packet_unpacker import PacketUnPacker
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.util.exception_util import ExceptionUtil

from bayserver_docker_http3 import qic_protocol_handler as ph
from bayserver_docker_http3.qic_type import QicType
from bayserver_docker_http3.qic_packet import QicPacket
from bayserver_docker_http3.qic_ticket import QicTicket


class QicPacketUnPacker(PacketUnPacker):

    pkt_store: PacketStore
    protocol_handler: "ph.QicProtocolHandler"
    ticket_map: Dict[bytes, QicTicket]
    retry_token_handler: QuicRetryTokenHandler
    tmp_post_packet: QicPacket
    tmp_post_address: str

    def __init__(self, pkt_store: PacketStore):
        self.pkt_store = pkt_store
        self.ticket_map = {}
        self.tmp_post_packet = None
        self.tmp_post_address = None
        self.retry_token_handler = QuicRetryTokenHandler()


    def __str__(self):
        return f"QicPacketUnpacker"

    ######################################################
    # Implements Reusable
    ######################################################
    def reset(self):
        pass

    ######################################################
    # Implements PacketUnPacker
    ######################################################
    def bytes_received(self, buf: bytes, adr: str):

        try:
            hdr = packet.pull_quic_header(buf=Buffer(data=buf), host_cid_length=self.port_docker().config.connection_id_length)
        except ValueError as e:
            BayLog.warn_e(e, "%s Cannot parse header: %s", self, ExceptionUtil.message(e))
            return NextSocketAction.CONTINUE

        BayLog.debug("%s packet received :len=%d ver=%s type=%s scid=%s dcid=%s tkn=%s",
                     self, len(buf), hdr.version, QicType.packet_type_name(int(buf[0])), hdr.source_cid.hex(), hdr.destination_cid.hex(),
                     hdr.token.hex())

        con_id = hdr.destination_cid

        # find handler
        ticket = self.get_ticket(hdr)
        #BayLog.debug("%s cid=%s hnd=%s", self, con_id.hex(), hnd)
        #BayLog.debug("%s con_id=%s hnd=%s", self, con_id, hnd)
        if ticket is None:
            BayLog.debug("%s ticket not found", self)
            if hdr.packet_type != packet.QuicPacketType.INITIAL:
                BayLog.warn("ticket not registered")
                new_con_id = os.urandom(8)
                self.retry(new_con_id, hdr, adr)
            else:
                ticket = self.create_qic_ticket(con_id, hdr, adr)

        if ticket:
            ticket.notify_read(buf, adr)

        posted = self.post_packets()

        if posted:
            return NextSocketAction.WRITE
        else:
            return NextSocketAction.CONTINUE


    def port_docker(self):
        return self.protocol_handler.port_docker()


    def set_protocol_handler(self, protocol_handler: "ph.QicProtocolHandler"):
        self.protocol_handler = protocol_handler

    def get_ticket(self, hdr):
        return self.find_ticket(hdr.destination_cid)

    def find_ticket(self, con_id: bytes):
        #BayLog.debug("find handler: %s", id.hex())
        return self.ticket_map.get(con_id)

    def add_ticket(self, con_id: bytes, hnd):
        #BayLog.debug("add handler: %s", id.hex())
        self.ticket_map[con_id] = hnd

    def version_is_supported(self, ver):
        return ver and ver in self.port_docker().config.supported_versions

    def negotiate_version(self, hdr, adr):
        BayLog.info("%s start negotiation", self)
        pkt = QicPacket()
        pkt.buf = bytearray(packet.encode_quic_version_negotiation(
            source_cid = hdr.destination_cid,
            destination_cid = hdr.source_cid,
            supported_versions = self.port_docker().config.supported_versions,
        ))
        pkt.buf_len = len(pkt.buf)
        self.tmp_post_packet = pkt
        self.tmp_post_address = adr

    def validate_token(self, adr, tkn):
        if len(tkn) <= 8:
            return None

        if self.port_docker().server_name != tkn[0:len(self.port_docker().server_name)]:
            return None

        #address = adr.getAddress();
        #if (!Arrays.equals(addr, Arrays.copyOfRange(token, serverNameBytes.length, addr.length + serverNameBytes.length)))
        #    return null;
        return tkn[len(self.port_docker().server_name) + len(adr):len(tkn)]

    def retry(self, new_scid, hdr, adr):
        pkt = QicPacket()

        tkn = self.retry_token_handler.create_token(adr, hdr.destination_cid, new_scid)
        BayLog.info("%s retry(new_scid=%s scid=%s dcid=%s tkn=%s)", self, new_scid.hex(), hdr.source_cid.hex(), hdr.destination_cid.hex(), tkn.hex())
        pkt.buf = bytearray(packet.encode_quic_retry(
            version = QuicProtocolVersion.VERSION_1,
            source_cid = new_scid,
            destination_cid = hdr.source_cid,
            original_destination_cid = hdr.destination_cid,
            retry_token = tkn
        ))
        pkt.buf_len = len(pkt.buf)
        self.tmp_post_packet = pkt
        self.tmp_post_address = adr

    def create_qic_ticket(self, con_id, hdr, adr):
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
            configuration=self.port_docker().config,
            original_destination_connection_id=odcid,
            retry_source_connection_id=scid,
            session_ticket_fetcher=self.port_docker().session_ticket_fetcher,
            session_ticket_handler=self.port_docker().session_ticket_handler,
        )

        BayLog.debug("%s create ticket: scid=%s hcid=%s", self, scid.hex(), con.host_cid.hex())
        tkt = QicTicket(self.protocol_handler, con, adr, None)


        self.add_ticket(con_id, tkt)
        self.add_ticket(con.host_cid, tkt)

        return tkt

    def post_packets(self):

        posted = False

        if self.tmp_post_packet:
            self.protocol_handler.packet_packer.post(self.protocol_handler.ship, self.tmp_post_address, self.tmp_post_packet, None)
            self.tmp_post_packet = None
            self.tmp_post_address = None
            posted = True

        # Check packets held in protocol handlers
        for qsip in self.ticket_map.values():
            posted |= qsip.post_packets()

        return posted


#    def next_read(self):
#        agt = ga.GrandAgent.get(self.protocol_handler.ship.agent_id)
#        agt.net_multiplexer.req_read(self.protocol_handler.ship.rudder)
