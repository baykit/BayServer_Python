"""BayServer club docker that runs PHP via libphp.so embedded in the
BayServer Python process (= same per-request boundary as php-fpm but
in-process, no FCGI envelope, no fork+exec per request).

Plan usage:
    [club *.php]
        docker pharos
        libPhpPath /path/to/libphp.so      # required
        iniPath    /path/to/php.ini        # optional (currently unused)

Lifecycle in multi_core=yes (the default for the Python bench):

    plan parse (parent)  -> init()
        dlopen libphp, patch ub_write + SAPI name, php_embed_init
        opcache mmap region exists in parent before fork

    Process(target=run_child) for each grand agent
        children inherit libphp handle + opcache mmap (CoW)
        no second php_embed_init needed

    arrive(Tour) on a child grand agent
        resolve docroot+uri -> .php file
        install PharosContentHandler

    handler.on_end_req_content(Tour)
        php_request_startup
        zend_eval_string("include '<file>';")
        php_request_shutdown
        ub_write upcall streams echo output into tour.res
"""

import os
import threading
import urllib.parse

from bayserver_core.bay_log import BayLog
from bayserver_core.config_exception import ConfigException
from bayserver_core.docker.base.club_base import ClubBase
from bayserver_core.http_exception import HttpException
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus

from bayserver_docker_pharos.pharos_content_handler import PharosContentHandler
from bayserver_docker_pharos.pharos_runtime import PharosRuntime


class PharosDocker(ClubBase):

    # Shared runtime, lazily initialised on first plan parse. Singleton
    # per process because libphp insists on one SAPI per process.
    _runtime = None
    _runtime_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self.lib_php_path = None
        self.ini_path = None

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        if not self.lib_php_path:
            raise ConfigException(
                elm.file_name, elm.line_no,
                "PharosDocker requires 'libPhpPath' (/path/to/libphp.so)")

        # Initialise runtime once per process (= parent). Concurrent
        # init() races are unlikely (plan parse is single-thread) but the
        # lock is cheap.
        if PharosDocker._runtime is None:
            with PharosDocker._runtime_lock:
                if PharosDocker._runtime is None:
                    rt = PharosRuntime(self.lib_php_path)
                    rt.init()
                    PharosDocker._runtime = rt

        BayLog.info("PharosDocker ready: libPhpPath=%s ini=%s",
                    self.lib_php_path, self.ini_path)

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "libphppath":
            self.lib_php_path = kv.value
        elif key == "inipath":
            self.ini_path = kv.value
        else:
            return super().init_key_val(kv)
        return True

    ######################################################
    # Implements Club
    ######################################################

    def arrive(self, tur):
        # Resolve the .php file path the same way FileDocker does:
        # docroot + (uri minus town prefix), URL-decoded, query-stripped.
        rel_path = tur.req.rewritten_uri or tur.req.uri
        town_name = tur.town.name() or ""
        if town_name and rel_path.startswith(town_name):
            rel_path = rel_path[len(town_name):]

        q = rel_path.find("?")
        if q != -1:
            rel_path = rel_path[:q]

        try:
            rel_path = urllib.parse.unquote(rel_path)
        except Exception as e:
            BayLog.error("Cannot decode path: %s: %s", rel_path, e)

        if rel_path.startswith("/"):
            rel_path = rel_path[1:]

        # BuiltInTownDocker.location is a plain string attribute, not a
        # method (Java's Town.location() is a method, but the Python port
        # collapsed it). Access without parens.
        file_path = os.path.join(tur.town.location, rel_path)
        if not os.path.isfile(file_path):
            raise HttpException(HttpStatus.NOT_FOUND, file_path)

        rt = PharosDocker._runtime
        if rt is None:
            # Should not happen: init() guarantees _runtime is set
            # before arrive() is reachable.
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR,
                                "PharosRuntime not initialised")

        handler = PharosContentHandler(tur, file_path, rt)
        tur.req.set_content_handler(handler)
