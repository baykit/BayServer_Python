import time

from bayserver_core.train.train import Train
from bayserver_core.bay_log import BayLog
from bayserver_core.tour.content_consume_listener import ContentConsumeListener
from bayserver_core.util.http_status import HttpStatus


class SendFileTrain(Train):

    def __init__(self, tur, file):
        self.tour = tur
        self.tour_id = tur.id
        self.file = file

    ######################################################
    # implements Train
    ######################################################

    def run(self):
        self.tour.res.set_consume_listener(ContentConsumeListener.dev_null)

        max_read_size = self.tour.ship.protocol_handler.max_packet_data_size()

        with open(self.file, "rb") as fd:
            try:
                while True:

                    try:
                        buf = fd.read(max_read_size)
                    except BaseException as e:
                        self.tour.res.send_error(self.tour_id, HttpStatus.INTERNAL_SERVER_ERROR, e);
                        break;

                    if len(buf) == 0:
                        break

                    self.tour.res.send_content(self.tour_id, buf, 0, len(buf));

                    while not self.tour.res.available:
                        time.sleep(0.1)

                self.tour.res.end_content(self.tour_id)
            except BaseException as e:
                BayLog.error_e(e)

