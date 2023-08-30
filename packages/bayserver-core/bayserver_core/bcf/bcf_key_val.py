from bayserver_core.bcf.bcf_object import BcfObject

class BcfKeyVal(BcfObject):

    def __init__(self, key, val, file_name, line_no):
        super().__init__(file_name, line_no)
        self.key = key
        self.value = val

