from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog
from bayserver_core.common.read_only_ship import ReadOnlyShip
from bayserver_core.rudder.rudder import Rudder
from bayserver_docker_cgi import cgi_req_content_handler as ch
from bayserver_core.util.internet_address import InternetAddress

class CgiStdErrShip(ReadOnlyShip):

    handler: "ch.CgiReqContentHandler"

    def __init__(self):
        super().__init__()
        self.handler = None


    def init_std_err(self, rd: Rudder, agt_id: int, handler: "ch.CgiReqContentHandler"):
        self.init(agt_id, rd, None)
        self.handler = handler


    def __str__(self):
        return f"agt#{self.agent_id} err_sip#{self.ship_id}/{self.object_id}"


    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        super.reset(self)
        self.handler = None


    ######################################################
    # implements Yacht
    ######################################################

    def notify_read(self, buf: bytes, adr: InternetAddress):

        BayLog.debug("%s CGI StdErr %d bytesd", self, len(buf))
        if len(buf) > 0:
            BayLog.error("CGI Stderr: %s", buf)

        self.handler.access()
        return NextSocketAction.CONTINUE

    def notify_error(self, e: Exception) -> None:
        BayLog.debug_e(e)

    def notify_eof(self) -> None:
        BayLog.debug("%s CGI StdErr: EOF\\(^o^)/", self)
        return NextSocketAction.CLOSE

    def notify_close(self) -> None:
        BayLog.debug("%s CGI StdErr: notifyClose", self)
        self.handler.on_std_err_closed()

    def check_timeout(self, duration_sec) -> bool:
        BayLog.debug("%s stderr Check timeout: dur=%d", self, duration_sec)
        return self.handler.timed_out()


    ######################################################
    # Custom methods
    ######################################################
