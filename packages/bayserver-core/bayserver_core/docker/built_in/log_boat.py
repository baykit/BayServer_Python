from bayserver_core.bay_log import BayLog
from bayserver_core.watercraft.boat import Boat
from bayserver_core.protocol.packet import Packet

from bayserver_core.util.char_util import CharUtil
from bayserver_core.util.string_util import StringUtil

class LogBoat(Boat):
    class LogPacket(Packet):

        def __init__(self, data):
            super().__init__(0, 0, len(data))
            self.new_data_accessor().put_string(data)


    def __init__(self):
        super().__init__()
        self.file_name = None
        self.postman = None


    def __str__(self):
        return f"lboat#{self.boat_id}/{self.object_id} file={self.file_name}";

    ######################################################
    # Implements DataListener
    ######################################################

    def notify_close(self):
        BayLog.info("Log closed: %s", self.file_name)

    ######################################################
    # Custom methods
    ######################################################

    def init(self, file_name, postman):
        self.init_boat()
        self.file_name = file_name
        self.postman = postman


    def log(self, data):
        if data == None:
            data = ""

        data += CharUtil.LF

        self.postman.post(StringUtil.to_bytes(data), None, self.file_name)