from bayserver_core.bay_log import BayLog
from bayserver_core.util.reusable import Reusable
from bayserver_core.util.data_consume_listener import DataConsumeListener

class CommandPacker(Reusable):

    class PostDoneListener(DataConsumeListener):
        def __init__(self, cmd_pkr, pkt, sip, lsnr):
            self.command_packer = cmd_pkr
            self.packet = pkt
            self.ship = sip
            self.listener = lsnr


        def done(self):
            self.command_packer.pkt_store.Return(self.packet)
            if self.listener is not None:
                if isinstance(self.listener, DataConsumeListener):
                    self.listener.done()
                else:
                    # function
                    self.listener()


    def __init__(self, pkt_packer, store):
        self.pkt_packer = pkt_packer
        self.pkt_store = store


    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        pass


    ######################################################
    # Other methods
    ######################################################

    def post(self, sip, cmd, callback=None):
        pkt = self.pkt_store.rent(cmd.type)

        try:
            cmd.pack(pkt)

            self.pkt_packer.post(sip.postman, pkt, CommandPacker.PostDoneListener(self, pkt, sip, callback))
        except IOError as e:
            self.pkt_store.Return(pkt)
            raise e


    def flush(self, sip):
        self.pkt_packer.flush(sip.postman)

    def end(self, sip):
        self.pkt_packer.end(sip.postman)