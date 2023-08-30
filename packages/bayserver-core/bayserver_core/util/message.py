import os

from bayserver_core.bcf import bcf_parser as pas
from bayserver_core.bcf.bcf_key_val import BcfKeyVal
from bayserver_core import bay_log
from bayserver_core.util.string_util import StringUtil

class Message:

    def __init__(self):
        self.messages = {}

    def init(self, file_prefix, locale):
        lang = locale.language
        file = file_prefix + ".bcf"
        if StringUtil.is_set(lang) and lang != "en":
            file = file_prefix + "_" + lang + ".bcf"

        if not os.path.isfile(file):
            bay_log.BayLog.warn("Cannot find message file: " + file)
            return


        p = pas.BcfParser()
        doc = p.parse(file)

        for o in doc.content_list:
            if isinstance(o, BcfKeyVal):
                self.messages[o.key] = o.value


    def get(self, key, *args):
        msg = self.messages.get(key)
        if msg is None:
            msg = key
        return msg % args
