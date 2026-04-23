from bayserver_core.protocol.packet import Packet
from bayserver_core.ship.ship import Ship
from bayserver_core.sink import Sink
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.reusable import Reusable

class PacketPacker(Reusable):

    def reset(self):
        pass

    def post(self, sip: Ship, adr: str, pkt: Packet, lsnr: DataConsumeListener):
        #if lsnr is None:
        #    raise Sink()

        # Slice to buf_len: after the c28d6dc optimization reset() preserves the
        # pre-allocated bytearray capacity, so len(buf) >= buf_len and we must
        # not send the unused tail.
        sip.transporter.req_write(sip.rudder, bytearray(pkt.buf[:pkt.buf_len]), adr, pkt, lsnr)


    def flush(self, postman):
        postman.flush()


    def end(self, postman):
        postman.post_end()
