class HostMatcher:
    MATCH_TYPE_ALL = 1
    MATCH_TYPE_EXACT = 2
    MATCH_TYPE_DOMAIN = 3

    def __init__(self, host):
        if host == "*":
            self.match_type = HostMatcher.MATCH_TYPE_ALL
        elif host.startswith("*."):
            self.match_type = HostMatcher.MATCH_TYPE_DOMAIN
            self.domain = host[2:]
        else:
            self.match_type = HostMatcher.MATCH_TYPE_EXACT
            self.host = host

    def match(self, remote_host):
        if self.match_type == HostMatcher.MATCH_TYPE_ALL:
            # all match
            return True

        if remote_host is None:
            return False

        if self.match_type == HostMatcher.MATCH_TYPE_EXACT:
            # exact match
            return remote_host == self.host
        else:
            # domain match
            return remote_host.endswith(self.domain)