import os

from bayserver_core.agent.grand_agent import GrandAgent
from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.docker.file.send_file_ship import SendFileShip
from bayserver_core.docker.harbor import Harbor
from bayserver_core.http_exception import HttpException
from bayserver_core.rudder.io_rudder import IORudder
from bayserver_core.sink import Sink
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.tour.tour import Tour
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.mimes import Mimes


class FileContentHandler(ReqContentHandler):

    path: str
    abortable: bool

    def __init__(self, path):
        self.path = path
        self.abortable = True

    ######################################################
    # Implements ReqContentHandler
    ######################################################

    def on_read_req_content(self, tur: Tour, buf: bytes, start: int, length: int, lis: DataConsumeListener):
        BayLog.debug("%s onReadReqContent(Ignore) len=%d", tur, length)
        tur.req.consumed(tur.tour_id, length, lis)

    def on_end_req_content(self, tur: Tour):
        BayLog.debug("%s endReqContent", tur)
        self.send_file_async(tur, self.path, tur.res.charset)
        self.abortable = False

    def on_abort_req(self, tur):
        BayLog.debug("%s onAbortReq aborted=%s", tur, self.abortable)
        return self.abortable

    ######################################################
    # Sending file methods
    ######################################################

    def send_file_async(self, tur: Tour, file: str, charset: str):

        if os.path.isdir(file):
            raise HttpException(HttpStatus.FORBIDDEN, file)
        elif not os.path.exists(file):
            raise HttpException(HttpStatus.NOT_FOUND, file)

        mime_type = None
        rname = os.path.basename(file)

        pos = rname.rfind('.')
        if pos > 0:
            ext = rname[pos + 1:].lower()
            mime_type = Mimes.type(ext)

        if mime_type is None:
            mime_type = "application/octet-stream"

        if mime_type.startswith("text/") and charset is not None:
            mime_type = mime_type + "; charset=" + charset

        file_len = os.path.getsize(file)
        #BayLog.debug("%s send_file %s async=%s len=%d", self.tour, file, async_mode, file_len)

        tur.res.headers.set_content_type(mime_type)
        tur.res.headers.set_content_length(file_len)

        try:
            tur.res.send_res_headers(Tour.TOUR_ID_NOCHECK)

            bufsize = tur.ship.protocol_handler.max_res_packet_data_size()
            mpx_type = BayServer.harbor.file_multiplexer()
            infile = open(file, "rb", buffering=False)
            rd = IORudder(infile)
            agt = GrandAgent.get(tur.ship.agent_id)

            if mpx_type == Harbor.MULTIPLEXER_TYPE_SPIDER:
                mpx = agt.spider_multiplexer

            elif mpx_type == Harbor.MULTIPLEXER_TYPE_SPIN:
                mpx = agt.spin_multiplexer

            elif mpx_type == Harbor.MULTIPLEXER_TYPE_TAXI:
                mpx = agt.taxi_multiplexer

            else:
                raise Sink()

            send_file_ship = SendFileShip()
            tp = PlainTransporter(mpx, send_file_ship, True, 8195, False)

            send_file_ship.init(rd, tp, tur)
            sid = send_file_ship.ship_id

            def callback(length: int, resume: bool):
                if resume:
                    send_file_ship.resume_read(sid)

            tur.res.set_res_consume_listener(callback)

            mpx.add_rudder_state(rd, RudderState(rd, tp))
            mpx.req_read(rd)

        except HttpException as e:
            raise e
        except Exception as e:
            BayLog.error_e(e)
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, file)


