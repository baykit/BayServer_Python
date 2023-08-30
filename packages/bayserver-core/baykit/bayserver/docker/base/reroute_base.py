from baykit.bayserver.config_exception import ConfigException

from baykit.bayserver.docker.reroute import Reroute
from baykit.bayserver.docker.base.docker_base import DockerBase

class RerouteBase(DockerBase, Reroute):

    def init(self, elm, parent):
        name = elm.arg;
        if name != "*":
            raise ConfigException(elm.file_name, elm.line_no, "Invalid reroute name: %s", name)
        super().init(elm, parent)


    def match(self, uri):
        return True