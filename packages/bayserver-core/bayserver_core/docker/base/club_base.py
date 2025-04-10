from bayserver_core.docker.club import Club
from bayserver_core.docker.base.docker_base import DockerBase

from bayserver_core.util.class_util import ClassUtil
from bayserver_core.util.string_util import StringUtil

class ClubBase(DockerBase, Club):

    _file_name: str
    _extension: str
    _charset: str
    _decode_path_info: bool

    def __init__(self):
        self._file_name = None
        self._extension = None
        self._charset = None
        self._locale = None
        self._decode_path_info = True

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        p = elm.arg.rfind('.')
        if p == -1:
            self._file_name = elm.arg
            self._extension = None
        else:
            self._file_name = elm.arg[:p]
            self._extension = elm.arg[p+1:]

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "decodepathinfo":
            self._decode_path_info = StringUtil.parse_bool(kv.value)
        elif key == "charset":
            self._charset = kv.value
        else:
            return super().init_key_val(kv)

        return True

    ######################################################
    # Implements Club
    ######################################################

    def file_name(self) -> str:
        return self._file_name

    def extension(self) -> str:
        return self._extension

    def charset(self) -> str:
        return self._charset

    def decode_path_info(self) -> bool:
        return self._decode_path_info

    def matches(self, fname):
        # check club
        pos = fname.find(".")
        if pos == -1:
            # fname has no extension
            if self._extension is not None:
                return False

            if self._file_name == "*":
                return True

            return fname == self._file_name
        else:
            # fname has extension
            if self._extension is None:
                return False


            nm = fname[:pos]
            ext = fname[pos+1:]

            if self._extension != "*" and ext != self._extension:
                return False

            if self._file_name == "*":
                return True
            else:
                return nm == self._file_name


    def __str__(self):
        return str(ClassUtil.get_local_name(self.__class__))


