from baykit.bayserver.bay_log import BayLog

from baykit.bayserver.agent.next_socket_action import NextSocketAction
from baykit.bayserver.sink import Sink
from baykit.bayserver.watercraft.yacht import Yacht
from baykit.bayserver.util.reusable import Reusable


class CgiStdErrYacht(Yacht, Reusable):

    def __init__(self):
        super().__init__()
        self.tour = None
        self.tour_id = None
        self.reset()


    def __str__(self):
        return "CGIErrYat#" + str(self.yacht_id) + "/" + str(self.object_id) + " tour=" + str(self.tour) + " id=" + str(self.tour_id)


    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        self.tour = None
        self.tour_id = 0

    ######################################################
    # implements Yacht
    ######################################################

    def notify_read(self, buf, adr):

        BayLog.debug("%s CGI StdErr %d bytesd", self, len(buf))
        if len(buf) > 0:
            BayLog.error("CGI Stderr: %s", buf)

        return NextSocketAction.CONTINUE


    def notify_eof(self):
        BayLog.debug("%s CGI StdErr: EOF\\(^o^)/", self)
        return NextSocketAction.CLOSE

    def notify_close(self):
        BayLog.debug("%s CGI StdErr: notifyClose", self)
        self.tour.req.content_handler.on_std_err_closed()

    def check_timeout(self, duration):
        BayLog.warn("%s invalid timeout check", self)
        return False


    ######################################################
    # Custom methods
    ######################################################
    def init(self, tur):
        self.init_yacht()
        self.tour = tur
        self.tour_id = tur.tour_id
