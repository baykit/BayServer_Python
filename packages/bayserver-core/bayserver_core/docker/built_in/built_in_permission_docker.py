from abc import ABCMeta, abstractmethod
import ipaddress

from bayserver_core.bay_message import BayMessage
from bayserver_core.bayserver import BayServer
from bayserver_core.symbol import Symbol
from bayserver_core.bay_log import BayLog

from bayserver_core.config_exception import ConfigException
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.permission import Permission
from bayserver_core.http_exception import HttpException
from bayserver_core.util.headers import Headers
from bayserver_core.util.host_matcher import HostMatcher
from bayserver_core.util.http_status import HttpStatus
from bayserver_core.util.ip_matcher import IpMatcher
from bayserver_core.util.string_util import StringUtil


class BuiltInPermissionDocker(DockerBase, Permission):
    class CheckItem:
        def __init__(self, matcher, admit):
            self.matcher = matcher
            self.admit = admit

        def socket_admitted(self, skt):
            return self.matcher.match_socket(skt) == self.admit

        def tour_admitted(self, tur):
            return self.matcher.match_tour(tur) == self.admit

    # interface
    class PermissionMatcher(metaclass=ABCMeta):
        @abstractmethod
        def match_socket(self, skt):
            pass

        @abstractmethod
        def match_tour(self, tur):
            pass


    class HostPermissionMatcher(PermissionMatcher):

        def __init__(self, host):
            self.mch = HostMatcher(host)

        def match_socket(self, skt):
            return self.mch.match(skt.remote_address.getnameinfo[0])

        def match_tour(self, tur):
            return self.mch.match(tur.req.remote_host())



    class IpPermissionMatcher(PermissionMatcher):
        def __init__(self, ip_desc):
            self.mch = IpMatcher(ip_desc)

        def match_socket(self, skt):
            return self.mch.match(IpMatcher.parse_ip(skt.getpeername()[0]))

        def match_tour(self, tur):
            return self.mch.match(ipaddress.ip_network(tur.req.remote_address))




    def __init__(self):
        super().__init__()
        self.check_list = []
        self.groups = []

    def init(self, elm, parent):
        super().init(elm, parent)

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "admit" or key == "allow":
            for permission_matcher in self.parse_value(kv):
                self.check_list.append(BuiltInPermissionDocker.CheckItem(permission_matcher, True))
        elif key == "refuse" or key == "deny":
            for permission_matcher in self.parse_value(kv):
                self.check_list.append(BuiltInPermissionDocker.CheckItem(permission_matcher, False))
        elif key == "group":
            for group_name in kv.value.split(" "):
                g = BayServer.harbor.groups.get_group(group_name)
                if g is None:
                    raise ConfigException(kv.file_name, kv.line_no, (Symbol.CFG_GROUP_NOT_FOUND, group_name))

            self.groups.append(g)
        else:
            raise ConfigException(kv.file_name, kv.line_no,
                                  BayMessage.get(Symbol.CFG_INVALID_PERMISSION_DESCRIPTION, kv.value))

        return True

    def socket_admitted(self, skt):
        # Check remote host
        isOk = True

        for chk in self.check_list:
            if chk.admit:
                if chk.socket_admitted(skt):
                    isOk = True
                    break
            else:
                if not chk.socket_admitted(skt):
                    isOk = False
                    break

        if not isOk:
            BayLog.error("Permission error: socket not admitted: %s", skt)
            raise HttpException(HttpStatus.FORBIDDEN)

    def tour_admitted(self, tur):
        # Check remote host
        is_ok = True

        for chk in self.check_list:
            if chk.admit:
                if chk.tour_admitted(tur):
                    is_ok = True
                    break
            else:
                if not chk.tour_admitted(tur):
                    is_ok = False
                    break

        if not is_ok:
            raise HttpException(HttpStatus.FORBIDDEN, tur.req.uri)

        if len(self.groups) == 0:
            return

        # Check member
        is_ok = False
        if tur.req.remote_user is not None:
            for grp in self.groups:
                if grp.validate(tur.req.remote_user, tur.req.remote_pass):
                    is_ok = True
                    break

        if not is_ok:
            tur.res.headers.set(Headers.WWW_AUTHENTICATE, "Basic realm=\"Auth\"")
            raise HttpException(HttpStatus.UNAUTHORIZED)

    def parse_value(self, kv):
        items = kv.value.split(" ")
        type = None
        match_str = []
        for i in range(len(items)):
            if i == 0:
                type = items[i]
            else:
                match_str.append(items[i])

        if len(match_str) == 0:
            raise ConfigException(kv.file_name, kv.line_no,
                                  BayMessage.get(Symbol.CFG_INVALID_PERMISSION_DESCRIPTION, kv.value))

        permission_manager_list = []
        if StringUtil.eq_ignorecase(type, "host"):
            for m in match_str:
                permission_manager_list.append(BuiltInPermissionDocker.HostPermissionMatcher(m))

        elif StringUtil.eq_ignorecase(type, "ip"):
            for m in match_str:
                permission_manager_list.append(BuiltInPermissionDocker.IpPermissionMatcher(m))

        else:
            raise ConfigException(kv.file_name, kv.line_no,
                                  BayMessage.get(Symbol.CFG_INVALID_PERMISSION_DESCRIPTION, kv.value))

        return permission_manager_list


