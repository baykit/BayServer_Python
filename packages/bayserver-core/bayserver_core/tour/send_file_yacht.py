import os

from bayserver_core.bay_log import BayLog

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.watercraft.yacht import Yacht


class SendFileYacht(Yacht):
    DEFAULT_FREAD_BUF_SIZE = 8192

    def __init__(self):
        super().__init__()
        self.tour = None
        self.tour_id = None

        self.file_name = None
        self.file_len = None
        self.file_wrote_len = None
        self.reset()


    def __str__(self):
        return "fyacht#" + str(self.yacht_id) + "/" + str(self.object_id) + " tour=" + str(self.tour) + " id=" + str(self.tour_id)


    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        self.file_len = None
        self.file_wrote_len = 0
        self.tour = None
        self.tour_id = 0

    ######################################################
    # implements Yacht
    ######################################################

    def notify_read(self, buf, adr):

        self.file_wrote_len += len(buf)
        BayLog.trace("%s notify_read %d bytes: total=%d/%d",
                     self, len(buf), self.file_wrote_len, self.file_len)
        available = self.tour.res.send_content(self.tour_id, buf, 0, len(buf))

        if available:
            return NextSocketAction.CONTINUE
        else:
            return NextSocketAction.SUSPEND

    def notify_eof(self):
        BayLog.trace("%s EOF(^o^) %s", self, self.file_name);
        self.tour.res.end_content(self.tour_id)
        return NextSocketAction.CLOSE

    def notify_close(self):
        BayLog.trace("File closed: %s", self.file_name)

    def check_timeout(self, duration):
        BayLog.trace("Check timeout: %s", self.file_name)


    ######################################################
    # Custom methods
    ######################################################
    def init(self, tur, file_name, tp):
        self.init_yacht()
        self.tour = tur
        self.tour_id = tur.tour_id
        self.file_name = file_name
        self.file_len = os.path.getsize(file_name)

        def callback(len, resume):
            if resume:
                tp.open_valve()
        tur.res.set_consume_listener(callback)

