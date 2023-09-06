from bayserver_core.bcf.bcf_object import BcfObject
from bayserver_core.bcf.bcf_key_val import BcfKeyVal
from bayserver_core.util.string_util import StringUtil


class BcfElement(BcfObject):
    def __init__(self, name, arg, file_name, line_no):
        super().__init__(file_name, line_no)
        self.name = name
        self.arg = arg
        self.content_list = []

    def get_value(self, key):
        for o in self.content_list:
            if isinstance(o, BcfKeyVal) and StringUtil.eq_ignorecase(o.key, key):
                return o.value
        return None
