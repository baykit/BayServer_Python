import ipaddress

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol
from bayserver_core.util.exception_util import ExceptionUtil

class IpMatcher:

    def __init__(self, ip_desc):
        self.match_all = (ip_desc == "*")
        self.net_addr = None

        if not self.match_all:
            self.net_addr = self.parse_ip(ip_desc)

    def match(self, ip):
        BayLog.debug("match_ip %s net=%s", ip, self.net_addr)

        if self.match_all:
            return True
        elif IpMatcher.is_ipv4(ip) != IpMatcher.is_ipv4(self.net_addr):
            # IPv4 and IPv6 don't match each other
            return False

        return ip.subnet_of(self.net_addr)

    @classmethod
    def is_ipv4(cls, ip):
        return isinstance(ip, ipaddress.IPv4Address) or isinstance(ip, ipaddress.IPv4Network)

    @classmethod
    def parse_ip(cls, ip_desc):
        items = ip_desc.split("/")
        if len(items) == 0:
            raise Exception(BayMessage.get(Symbol.CFG_INVALID_IP_DESC, ip_desc))

        if len(items) == 1:
            ip_desc = ip_desc + "/32"

        try:
            return ipaddress.ip_network(ip_desc, False)
        except ValueError as e:
            raise Exception(BayMessage.get(Symbol.CFG_INVALID_IP_DESC, ExceptionUtil.message(e)))


