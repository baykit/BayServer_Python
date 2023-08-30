from bayserver_core.docker.club import Club
from bayserver_core.docker.base.docker_base import DockerBase

from bayserver_core.util.class_util import ClassUtil
from bayserver_core.util.string_util import StringUtil

class ClubBase(DockerBase, Club):

    def __init__(self):
        self.file_name = None
        self.extension = None
        self.charset = None
        self.locale = None
        self.decode_path_info = True

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        p = elm.arg.rfind('.')
        if p == -1:
            self.file_name = elm.arg
            self.extension = None
        else:
            self.file_name = elm.arg[:p]
            self.extension = elm.arg[p+1:]

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "decodepathinfo":
            self.decode_path_info = StringUtil.parse_bool(kv.value)
        elif key == "charset":
            self.charset = kv.value
        else:
            return super().init_key_val(kv)

        return True

    ######################################################
    # Implements Club
    ######################################################

    def matches(self, fname):
        # check club
        pos = fname.find(".")
        if pos == -1:
            # fname has no extension
            if self.extension is not None:
                return False

            if self.file_name == "*":
                return True

            return fname == self.file_name
        else:
            # fname has extension
            if self.extension is None:
                return False


            nm = fname[:pos]
            ext = fname[pos+1:]

            if self.extension != "*" and ext != self.extension:
                return False

            if self.file_name == "*":
                return True
            else:
                return nm == self.file_name


    def __str__(self):
        return str(ClassUtil.get_local_name(self.__class__))


