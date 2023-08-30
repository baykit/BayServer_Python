from bayserver_core.bayserver import BayServer
from bayserver_core.util.locale import Locale
from bayserver_core.util.message import Message

class CgiMessage:

    msg = Message()

    @classmethod
    def init(cls):
        CgiMessage.msg.init(BayServer.bserv_home + "/lib/conf/cgi_messages", Locale.default())

    @classmethod
    def get(cls, key, *args):
        return CgiMessage.msg.get(key, *args)



