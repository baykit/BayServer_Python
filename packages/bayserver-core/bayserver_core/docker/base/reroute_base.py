from bayserver_core.config_exception import ConfigException

from bayserver_core.docker.reroute import Reroute
from bayserver_core.docker.base.docker_base import DockerBase

class RerouteBase(DockerBase, Reroute):

    def init(self, elm, parent):
        name = elm.arg;
        if name != "*":
            raise ConfigException(elm.file_name, elm.line_no, "Invalid reroute name: %s", name)
        super().init(elm, parent)


    def match(self, uri):
        return True