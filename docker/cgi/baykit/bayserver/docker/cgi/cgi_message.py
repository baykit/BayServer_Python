from baykit.bayserver.bayserver import BayServer
from baykit.bayserver.util.locale import Locale
from baykit.bayserver.util.message import Message

class CgiMessage:

    msg = Message()

    @classmethod
    def init(cls):
        CgiMessage.msg.init(BayServer.bserv_home + "/lib/conf/cgi_messages", Locale.default())

    @classmethod
    def get(cls, key, *args):
        return CgiMessage.msg.get(key, *args)



