from bayserver_core.util.message import Message

class BayMessage:

    msg = Message()

    @classmethod
    def init(cls, conf_name, locale):
        BayMessage.msg.init(conf_name, locale)

    @classmethod
    def get(cls, key, *args):
        return BayMessage.msg.get(key, *args)

