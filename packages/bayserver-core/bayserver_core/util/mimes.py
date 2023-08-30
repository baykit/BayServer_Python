from bayserver_core.bcf.bcf_parser import BcfParser
from bayserver_core.bcf.bcf_key_val import BcfKeyVal

class Mimes:
    mime_map = {}

    @classmethod
    def init(cls, bcf_file):
        p = BcfParser()
        doc = p.parse(bcf_file)
        for kv in doc.content_list:
            if isinstance(kv, BcfKeyVal):
                Mimes.mime_map[kv.key] = kv.value

    @classmethod
    def type(cls, ext):
        return Mimes.mime_map.get(ext)
