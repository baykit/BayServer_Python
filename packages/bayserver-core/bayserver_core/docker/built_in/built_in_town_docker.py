import os.path

from bayserver_core.bayserver import BayServer
from bayserver_core.config_exception import ConfigException
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol

from bayserver_core.docker.town import Town
from bayserver_core.docker.club import Club
from bayserver_core.docker.permission import Permission
from bayserver_core.docker.reroute import Reroute
from bayserver_core.docker.base.docker_base import DockerBase


class BuiltInTownDocker(DockerBase, Town):

    def __init__(self):
        self.name = None
        self.location = None
        self.welcome = None
        self.clubs = []
        self.permission_list = []
        self.city = None
        self.reroute_list = []



    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        arg = elm.arg
        if not arg.startswith("/"):
            arg = "/" + arg

        self.name = arg
        if not self.name.endswith("/"):
            self.name += "/"

        self.city = parent
        super().init(elm, parent)


    ######################################################
    # Implements DockerBase
    ######################################################

    def init_docker(self, dkr):
        if isinstance(dkr, Club):
            self.clubs.append(dkr)
        elif isinstance(dkr, Permission):
            self.permission_list.append(dkr)
        elif isinstance(dkr, Reroute):
            self.reroute_list.append(dkr)
        else:
            return False
        return True


    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "location":
            self.location = kv.value
            if not os.path.isabs(self.location):
                self.location = BayServer.parse_path(self.location)
            if not os.path.isdir(self.location):
                raise ConfigException(kv.file_name, kv.line_no, BayMessage.get(Symbol.CFG_INVALID_LOCATION, kv.value))
        elif key == "index" or key == "welcome":
            self.welcome = kv.value
        else:
            return super().init_key_val(kv)
        return True

    ######################################################
    # Implements Town
    ######################################################

    def reroute(self, uri):
        for r in self.reroute_list:
            uri = r.reroute(self, uri)

        return uri

    def matches(self, uri):
        if uri.startswith(self.name):
            return BuiltInTownDocker.MATCH_TYPE_MATCHED
        elif uri + "/" == self.name:
            return BuiltInTownDocker.MATCH_TYPE_CLOSE
        else:
            return BuiltInTownDocker.MATCH_TYPE_NOT_MATCHED

    def tour_admitted(self, tur):
        for p in self.permission_list:
            p.tour_admitted(tur)
