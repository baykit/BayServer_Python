import urllib.parse
import os.path

from bayserver_core.bay_log import BayLog
from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.docker.file.file_content_handler import FileContentHandler
from bayserver_core.http_exception import HttpException

from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil

class FileDocker(ClubBase):

    def __init__(self):
        super().__init__()
        self.list_files = False

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "listfiles":
            self.list_files = StringUtil.parse_bool(kv.value)
        else:
            return super().init_key_val(kv)
        return True


    def arrive(self, tur):
        rel_path = tur.req.rewritten_uri if tur.req.rewritten_uri else tur.req.uri
        if StringUtil.is_set(tur.town.name):
            rel_path = rel_path[len(tur.town.name):]
        pos = rel_path.find('?')
        if pos >= 0:
            rel_path = rel_path[0: pos]

        try:
            rel_path = urllib.parse.unquote(rel_path, tur.req._charset)
        except Exception as e:
            # Do not let malformed url-encoded input bring down the agent
            # (Java 9dcab39).
            BayLog.error("Cannot decode path: %s: %s", rel_path, e)
            raise HttpException(HttpStatus.BAD_REQUEST, rel_path)
        real = os.path.join(tur.town.location, rel_path)

        handler = FileContentHandler(tur, real, tur.res.charset, self.list_files)
        tur.req.set_content_handler(handler)
