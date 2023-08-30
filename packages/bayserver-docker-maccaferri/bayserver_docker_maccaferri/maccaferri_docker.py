import os.path
import importlib
import sys
import wsgiref.util

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.config_exception import ConfigException

from bayserver_core.http_exception import HttpException
from bayserver_core.docker.base.club_base import ClubBase

from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.cgi_util import CgiUtil
from bayserver_core.util.exception_util import ExceptionUtil

from bayserver_docker_maccaferri.maccaferri_train import MaccaferriTrain

class MaccaferriDocker(ClubBase):

    class ErrorWriter:
        def write(self, string):
            if string.endswith("\r\n"):
                string = string[:-2]
            elif string.endswith("\n"):
                string = string[:-1]
            BayLog.error(string)

    DEFAULT_POST_CACHE_THRESHOLD = 1024 * 128  # 128 KB

    def __init__(self):
        super().__init__()
        self.script = None
        self.app = None
        self.app_callable = None
        self.project = None
        self.module = None
        self.post_cache_threshold = MaccaferriDocker.DEFAULT_POST_CACHE_THRESHOLD


    def init(self, elm, parent):
        super().init(elm, parent)

        if StringUtil.is_empty(self.project):
            raise ConfigException(elm.file_name, elm.line_no, "Specify project")

        if StringUtil.is_empty(self.module):
            raise ConfigException(elm.file_name, elm.line_no, "Specify module")

        if StringUtil.is_empty(self.app):
            raise ConfigException(elm.file_name, elm.line_no, "Specify app")

        sys.path.append(os.path.abspath(self.project))

        try:
            module = importlib.import_module(self.module)
        except Exception as e:
            BayLog.error("Cannot import module: %s err=%s sys.path=%s", self.script, ExceptionUtil.message(e), sys.path)
            raise e

        self.app_callable = getattr(module, self.app)

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "project":
            self.project = BayServer.get_location(kv.value)
        elif key == "module":
            self.module = kv.value
        elif key == "app":
            self.app = kv.value
        elif key == "postcachethreshold":
            self.post_cache_threshold = int(kv.value)
        else:
            return super().init_key_val(kv)
        return True

    def arrive(self, tur):

        if tur.req.uri.find("..") >= 0:
            raise HttpException(HttpStatus.FORBIDDEN, tur.req.uri)

        env = CgiUtil.get_env_hash(tur.town.name, self.project, self.project, tur)

        script_name = tur.town.name
        if script_name.endswith("/"):
            script_name = script_name[0:len(script_name)-1]

        p = tur.req.uri.find("?")
        if p > 0:
            path_info = tur.req.uri[len(script_name):p]
        else:
            path_info = tur.req.uri[len(script_name):]

        env["SCRIPT_NAME"] = script_name
        env["PATH_INFO"] = path_info


#        if BayServer.harbor.trace_header:
#            for name in env.keys():
#                value = env[name]
#                BayLog.info("%s cgi: env: %s=%s", tur, name, value)

        self.create_wsgi_env(tur, env)

        train = MaccaferriTrain(self, tur, self.app, env)
        train.start_tour()


    def create_wsgi_env(self, tur, env):
        env["wsgi.input"] = None
        env["wsgi.file_wrapper"] = wsgiref.util.FileWrapper
        env["wsgi.version"] = (1, 0)
        env["wsgi.errors"] = MaccaferriDocker.ErrorWriter()
        env["wsgi.run_once"] = False
        env["wsgi.multithread"] = False
        env["wsgi.multiprocess"] = False
        env["wsgi.url_scheme"] = "http"
        env["bayserver.version"] = BayServer.get_version()
