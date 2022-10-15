import traceback

from baykit.bayserver import bayserver as bs
from baykit.bayserver.bay_message import BayMessage
from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.config_exception import ConfigException
from baykit.bayserver.symbol import Symbol

from baykit.bayserver.docker.docker import Docker
from baykit.bayserver.bcf.bcf_key_val import BcfKeyVal


class DockerBase(Docker):

    def __init__(self):
        self.type = None


    def init(self, elm, parent):
        self.type = elm.name

        for o in elm.content_list:
            if isinstance(o, BcfKeyVal):
                try:
                    if not self.init_key_val(o):
                        raise ConfigException(o.file_name, o.line_no, BayMessage.get(Symbol.CFG_INVALID_PARAMETER, o.key))
                except ConfigException as e:
                    raise e
                except BaseException as e:
                    BayLog.error_e(e)
                    raise ConfigException(o.file_name, o.line_no, BayMessage.get(Symbol.CFG_INVALID_PARAMETER_VALUE, o.key))
            else:
                try:
                    dkr = bs.BayServer.dockers.create_docker(o, self)
                except ConfigException as e:
                    raise e
                except BaseException as e:
                    traceback.print_exc()
                    BayLog.error_e(e)
                    raise ConfigException(o.file_name, o.line_no, BayMessage.get(Symbol.CFG_INVALID_DOCKER, o.name))

                if not self.init_docker(dkr):
                    raise ConfigException(o.file_name, o.line_no, BayMessage.get(Symbol.CFG_INVALID_DOCKER, o.name))

    def init_docker(self, dkr):
        return False


    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "docker":
            return True
        else:
            return False
