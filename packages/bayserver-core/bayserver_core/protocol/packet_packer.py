from bayserver_core.protocol.packet import Packet
from bayserver_core.ship.ship import Ship
from bayserver_core.sink import Sink
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.reusable import Reusable

class PacketPacker(Reusable):

    def reset(self):
        pass

    def post(self, sip: Ship, pkt: Packet, lsnr: DataConsumeListener):
        if lsnr is None:
            raise Sink()

        sip.transporter.req_write(sip.rudder, pkt.buf.copy(), None, pkt, lsnr)


    def flush(self, postman):
        postman.flush()


    def end(self, postman):
        postman.post_end()
