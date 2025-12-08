import os.path
import traceback

from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.http_exception import HttpException
from bayserver_core.tour.tour import Tour
from bayserver_core.util.cgi_util import CgiUtil
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.sys_util import SysUtil
from bayserver_docker_cgi.cgi_req_content_handler import CgiReqContentHandler


class CgiDocker(ClubBase):

    DEFAULT_TIMEOUT_SEC = 60
    interpreter: str
    script_base: str
    doc_root: str
    timeout_sec: int
    max_processes: int
    process_count: int
    wait_count: int

    def __init__(self):
        super().__init__()
        self.interpreter = None
        self.script_base = None
        self.doc_root = None
        self.timeout_sec = CgiDocker.DEFAULT_TIMEOUT_SEC
        self.max_processes = -1
        self.process_count = 0
        self.wait_count = 0


    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)


    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "interpreter":
            self.interpreter = kv.value

        elif key == "scriptbase":
            self.script_base = kv.value

        elif key == "docroot":
            self.doc_root = kv.value

        elif key == "timeout":
            self.timeout_sec = int(kv.value)

        elif key == "maxprocesses":
            self.max_processes = int(kv.value)

        else:
            return super().init_key_val(kv)
        return True

    def arrive(self, tur: Tour):

        if tur.req.uri.find("..") >= 0:
            raise HttpException(HttpStatus.FORBIDDEN, tur.req.uri)

        base = self.script_base
        if base is None:
            base = tur.town.location

        if StringUtil.is_empty(base):
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, "%s scriptBase of cgi docker or location of town is not specified.", tur.town)

        root = self.doc_root
        if root is None:
            root = tur.town.location

        if StringUtil.is_empty(root):
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR, "$s docRoot of cgi docker or location of town is not specified.", tur.town)

        try:
            env = CgiUtil.get_env_hash(tur.town.name, root, base, tur)
        except ValueError as e:
            BayLog.error_e(e, traceback.format_stack(), "Invalid CGI environment value")
            raise HttpException(HttpStatus.BAD_REQUEST, tur.req.uri)

        if BayServer.harbor.trace_header():
            for name in env.keys():
                value = env[name]
                BayLog.info("%s cgi: env: %s=%s", tur, name, value)

        file_name = env[CgiUtil.SCRIPT_FILENAME]
        if not os.path.isfile(file_name):
            raise HttpException(HttpStatus.NOT_FOUND, file_name)

        handler = CgiReqContentHandler(self, tur, env)
        tur.req.set_content_handler(handler)
        handler.req_start_tour()


    def create_command(self, env):
        script = env[CgiUtil.SCRIPT_FILENAME]
        if self.interpreter is None:
            command = [script]
        else:
            command = [self.interpreter, script]

        if SysUtil.run_on_windows():
            for i in range(len(command)):
                command[i] = command[i].replace('/', '\\')

        return command

    ######################################################
    # Custom methods
    ######################################################

    def get_wait_count(self) -> int:
        return self.wait_count

    def add_process_count(self) -> bool:
        if self.max_processes <= 0 or self.process_count < self.max_processes:
            self.process_count += 1
            BayLog.debug("%s Process count: %d", self, self.process_count)
            return True

        self.wait_count += 1
        return False

    def sub_process_count(self) -> None:
        self.process_count -= 1

    def sub_wait_count(self) -> None:
        self.wait_count -= 1