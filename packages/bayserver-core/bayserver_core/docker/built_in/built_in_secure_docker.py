import ssl


from bayserver_core.bay_log import BayLog
from bayserver_core.bayserver import BayServer
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.agent.transporter.secure_transporter import SecureTransporter
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.config_exception import ConfigException

from bayserver_core.docker.secure import Secure
from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.exception_util import ExceptionUtil

class BuiltInSecureDocker(DockerBase, Secure):
    DEFAULT_CLIENT_AUTH = False
    DEFAULT_SSL_PROTOCOL = "TLS"

    def __init__(self):
        super().__init__()
        self.key_store = None
        self.key_store_pass = None
        self.client_auth = BuiltInSecureDocker.DEFAULT_CLIENT_AUTH
        self.ssl_protocol = BuiltInSecureDocker.DEFAULT_SSL_PROTOCOL
        self.key_file = None
        self.cert_file = None
        self.certs = None
        self.certs_pass = None
        self.trace_ssl = False
        self.sslctx = None
        self.app_protocols = []


    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)
        if (self.key_store is None) and ((self.key_file is None) or (self.cert_file is None)):
            raise ConfigException(elm.file_name, elm.line_no, "Key file or cert file is not specified")


        try:
            self.init_ssl()
        except ConfigException as e:
            raise e
        except BaseException as e:
            BayLog.error_e(e)
            raise ConfigException(elm.file_name, elm.line_no, BayMessage.get(Symbol.CFG_SSL_INIT_ERROR, ExceptionUtil.message(e)))

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "key":
            self.key_file = BayServer.parse_path(kv.value)
        elif key == "cert":
            self.cert_file = BayServer.parse_path(kv.value)
        elif key == "keystore":
            self.key_store = BayServer.parse_path(kv.value)
        elif key == "keystorepass":
            self.key_store_pass = kv.value
        elif key == "clientauth":
            self.client_auth = StringUtil.parse_bool(kv.value)
        elif key == "sslprotocol":
            self.ssl_protocol = kv.value
        elif key == "trustcerts":
            self.certs = BayServer.parse_path(kv.value)
        elif key == "certspass":
            self.certs_pass = kv.value
        elif key == "tracessl":
            self.trace_ssl = StringUtil.parse_bool(kv.value)
        else:
            return False
        return True

    ######################################################
    # Implements Secure
    ######################################################

    def set_app_protocols(self, protocols):
        self.app_protocols = protocols
        if not ssl.HAS_ALPN:
            BayLog.warn("This version of Python does not support ALPN, so cannot use H2")

        self.sslctx.set_alpn_protocols(protocols)

    def create_transporter(self, bufsize):
        return SecureTransporter(self.sslctx, True, bufsize, self.trace_ssl)

    def reload_cert(self):
        self.init_ssl()

    def init_ssl(self):
        BayLog.debug("init ssl")
        #self.sslctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.sslctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.sslctx.check_hostname = False

        if self.key_store is None:
            #if self.cert_file is None or self.key_file is None:
            #    raise ConfigException(elm.file_name, elm.line_no, "Specify cert and key file")

            self.sslctx.load_cert_chain(certfile=self.cert_file, keyfile=self.key_file)


