
from bayserver_core.bay_log import BayLog
from bayserver_docker_cgi.cgi_docker import CgiDocker
from bayserver_core.util.cgi_util import CgiUtil

class PhpCgiDocker(CgiDocker):

    ENV_PHP_SELF = "PHP_SELF"
    ENV_REDIRECT_STATUS = "REDIRECT_STATUS"

    def init(self, elm, parent):
        super().init(elm, parent)

        if self.interpreter is None:
            self.interpreter = "php-cgi";

        BayLog.info("PHP interpreter: " + self.interpreter)

    def create_command(self, env):
        env[PhpCgiDocker.ENV_PHP_SELF] = env[CgiUtil.SCRIPT_NAME]
        env[PhpCgiDocker.ENV_REDIRECT_STATUS] = "200"
        return super().create_command(env)
