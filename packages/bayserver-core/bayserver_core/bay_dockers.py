import importlib
import re
import sys

from bayserver_core.bay_exception import BayException
from bayserver_core.bay_message import BayMessage
from bayserver_core.bay_log import BayLog
from bayserver_core.symbol import Symbol
from bayserver_core.bcf.bcf_parser import BcfParser
from bayserver_core.bcf.bcf_key_val import BcfKeyVal
from bayserver_core.util.string_util import StringUtil

class BayDockers:

    def __init__(self):
        self.docker_map = {}

    def init(self, conf_file):
        p = BcfParser()
        doc = p.parse(conf_file)

        for obj in doc.content_list:
            if isinstance(obj, BcfKeyVal):
                self.docker_map[obj.key] = obj.value

    def create_docker(self, elm, parent):
        alias_name = elm.get_value("docker")
        d = self.create_docker_by_alias(elm.name, alias_name)
        d.init(elm, parent)
        return d

    def create_docker_by_alias(self, category, alias_name):

        if StringUtil.is_empty(alias_name):
          key = category
        else:
          key = category + ":" + alias_name

        class_name = self.docker_map.get(key)
        if class_name is None:
            raise BayException(BayMessage.get(Symbol.CFG_DOCKER_NOT_FOUND, key))

        module_name = re.sub(r'([a-z])([A-Z])', r'\1_\2', class_name).lower()

        p = class_name.rfind(".")
        attr_name = class_name[p+1:]

        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            BayLog.error("Cannot import module: %s err=%s sys.path=%s", module_name, e.args[0], sys.path)
            raise e

        cls = getattr(module, attr_name)

        return cls()
