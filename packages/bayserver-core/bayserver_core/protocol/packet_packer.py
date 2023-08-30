from bayserver_core.sink import Sink
from bayserver_core.util.reusable import Reusable

class PacketPacker(Reusable):

    def reset(self):
        pass

    def post(self, postman, pkt, lsnr):
        if postman is None or pkt is None or lsnr is None:
            raise Sink()

        postman.post(pkt.buf[0:pkt.buf_len], None, pkt, lsnr)


    def flush(self, postman):
        postman.flush()


    def end(self, postman):
        postman.post_end()
