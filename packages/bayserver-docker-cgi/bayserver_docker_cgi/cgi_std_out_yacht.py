import subprocess

from bayserver_core.bay_log import BayLog

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bayserver import BayServer
from bayserver_core.util.char_util import CharUtil
from bayserver_core.util.string_util import StringUtil
from bayserver_core.watercraft.yacht import Yacht
from bayserver_core.util.reusable import Reusable


class CgiStdOutYacht(Yacht, Reusable):

    def __init__(self):
        super().__init__()
        self.tour = None
        self.tour_id = None
        self.file_wrote_len = None
        self.remain = None
        self.header_reading = None
        self.handler = None
        self.reset()


    def __str__(self):
        return "CGIYat#" + str(self.yacht_id) + "/" + str(self.object_id) + " tour=" + str(self.tour) + " id=" + str(self.tour_id)


    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        self.file_wrote_len = 0
        self.tour = None
        self.tour_id = 0
        self.remain = b""
        self.header_reading = True
        self.handler = None

    ######################################################
    # implements Yacht
    ######################################################

    def notify_read(self, buf, adr):

        self.file_wrote_len += len(buf)
        BayLog.trace("%s notify_read %d bytes: total=%d", self, len(buf), self.file_wrote_len)

        pos = 0
        if self.header_reading:

            while True:
                p = buf.find(CharUtil.LF_BYTE, pos)

                #BayLog.debug("pos: %d", pos)

                if p == -1:
                    break

                line = buf[pos:p]
                pos = p + 1

                if len(self.remain) > 0:
                    line = self.remain + line

                self.remain = b""
                line = line.strip()

                #  if line is empty ("\r\n")
                #  finish header reading.
                if StringUtil.is_empty(line):
                    self.header_reading = False
                    self.tour.res.send_headers(self.tour_id)
                    break

                else:
                    if BayServer.harbor.trace_header:
                        BayLog.info("%s CGI: res header line: %s", self.tour, line)

                    sep_pos = line.index(CharUtil.COLON_BYTE)
                    if sep_pos != -1:
                        key = line[0 : sep_pos].strip()
                        val = line[sep_pos + 1 :].strip()

                        if key.lower() == b"status":
                            try:
                                val = val.split(b" ")[0]
                                self.tour.res.headers.status = int(val)
                            except BaseException as e:
                                BayLog.error_e(e)

                        else:
                            self.tour.res.headers.add(key.decode(), val.decode())


        available = True

        if self.header_reading:
            self.remain += buf[pos:]
        else:
            if len(buf) - pos > 0:
                available = self.tour.res.send_content(self.tour_id, buf, pos, len(buf) - pos)

        self.handler.access()
        if available:
            return NextSocketAction.CONTINUE
        else:
            return NextSocketAction.SUSPEND


    def notify_eof(self):
        BayLog.debug("%s CGI StdOut: EOF(^o^)", self)
        return NextSocketAction.CLOSE

    def notify_close(self):
        BayLog.debug("%s CGI StdOut: notifyClose", self)
        self.tour.req.content_handler.on_std_out_closed()

    def check_timeout(self, duration_sec):
        BayLog.debug("%s Check StdOut timeout: dur=%d", self.tour, duration_sec)

        if self.handler.timed_out():
            # Kill cgi process instead of handing timeout
            BayLog.warn("%s Kill process!: %d", self.tour, self.handler.process.pid)
            self.handler.process.kill()
            return True
        return False

    ######################################################
    # Custom methods
    ######################################################
    def init(self, tur, vv, handler):
        self.init_yacht()
        self.handler = handler
        self.tour = tur
        self.tour_id = tur.tour_id


        def callback(len, resume):
            if resume:
                vv.open_valve()
        tur.res.set_consume_listener(callback)

