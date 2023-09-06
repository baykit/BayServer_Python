import os.path

from bayserver_core.docker.base.reroute_base import RerouteBase
from bayserver_core.util.string_util import StringUtil

class WordPressDocker(RerouteBase):

    def __init__(self):
        self.town_path = None


    def init(self, elm, parent):
        super().init(elm, parent)

        self.town_path = parent.location

    def reroute(self, twn, uri):

        uri_parts = uri.split("?")
        uri2 = uri_parts[0]
        if not self.match(uri2):
            return uri


        rel_path = uri2[len(twn.name):]
        if rel_path.startswith("/"):
            rel_path = rel_path[1:]

        rel_parts = rel_path.split("/")
        check_path = ""

        for path_item in rel_parts:
            if StringUtil.is_set(check_path):
                check_path += "/"
            check_path += path_item

            if os.path.exists(twn.location + "/" + check_path):
                return uri

        if not os.path.exists(twn.location + "/" + rel_path):
            return twn.name + "index.php/" + uri[len(twn.name):]
        else:
            return uri
