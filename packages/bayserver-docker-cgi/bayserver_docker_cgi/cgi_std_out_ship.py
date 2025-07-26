import subprocess
from typing import Any

from bayserver_core.bay_log import BayLog

from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bayserver import BayServer
from bayserver_core.common.read_only_ship import ReadOnlyShip
from bayserver_core.common.transporter import Transporter
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.tour.tour import Tour
from bayserver_core.util.char_util import CharUtil
from bayserver_core.util.string_util import StringUtil
from bayserver_docker_cgi import cgi_req_content_handler as ch
from bayserver_core.util.internet_address import InternetAddress

class CgiStdOutShip(ReadOnlyShip):

    file_wrote_len: int
    tour: Tour
    tour_id: int

    remain: bytes
    header_reading: bool
    handler: "ch.CgiReqContentHandler"


    def __init__(self):
        super().__init__()
        self.tour = None
        self.tour_id = None
        self.file_wrote_len = None
        self.remain = None
        self.header_reading = None
        self.handler = None
        self.reset()

    def init_std_out(self, rd: Rudder, agt_id: int, tur: Tour, tp: Transporter, handler: "ch.CgiReqContentHandler") -> None:
        self.init(agt_id, rd, tp)
        self.handler = handler
        self.tour = tur
        self.tour_id = tur.tour_id
        self.header_reading = True

    def __str__(self):
        return f"agt#{self.agent_id} out_ship#{self.ship_id}/#{self.object_id}"


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

    def notify_read(self, buf: bytes, adr: InternetAddress):

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
                    self.tour.res.send_res_headers(self.tour_id)
                    break

                else:
                    if BayServer.harbor.trace_header():
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
                available = self.tour.res.send_res_content(self.tour_id, buf, pos, len(buf) - pos)

        self.handler.access()
        if available:
            return NextSocketAction.CONTINUE
        else:
            return NextSocketAction.SUSPEND

    def notify_error(self, e: Exception) -> None:
        BayLog.debug_e(e, "%s CGI notifyError tur=%s", self, self.tour)

    def notify_eof(self):
        BayLog.debug("%s CGI StdOut: EOF(^o^)", self)
        return NextSocketAction.CLOSE

    def notify_close(self):
        BayLog.debug("%s CGI StdOut: notifyClose", self)
        self.handler.on_std_out_closed()

    def check_timeout(self, duration_sec):
        BayLog.debug("%s (tur=%s) Check StdOut timeout: dur=%d", self, self.tour, duration_sec)

        if self.handler.timed_out():
            # Kill cgi process instead of handing timeout
            BayLog.warn("%s Kill process!: %d", self.tour, self.handler.process.pid)
            self.handler.process.kill()
            return True
        return False

    ######################################################
    # Custom methods
    ######################################################
