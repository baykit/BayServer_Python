import urllib.parse
import os.path

from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.docker.file.file_content_handler import FileContentHandler
from bayserver_core.docker.file.directory_train import DirectoryTrain

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

        rel_path = urllib.parse.unquote(rel_path, tur.req.charset)
        real = f"{tur.town.location}/{rel_path}"

        if os.path.isdir(real) and self.list_files:
            train = DirectoryTrain(tur, real)
            train.start_tour()
        else:
            handler = FileContentHandler(real)
            tur.req.set_content_handler(handler)


