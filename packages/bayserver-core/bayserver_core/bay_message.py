from bayserver_core.util.message import Message

class BayMessage:

    msg: Message = None

    @classmethod
    def init(cls, conf_name, locale):
        cls.msg = Message()
        BayMessage.msg.init(conf_name, locale)

    @classmethod
    def get(cls, key, *args):
        return BayMessage.msg.get(key, *args)

