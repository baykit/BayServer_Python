import os.path
import urllib.parse

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.http_exception import HttpException
from bayserver_core.symbol import Symbol

from bayserver_core.docker.city import City
from bayserver_core.docker.town import Town
from bayserver_core.docker.club import Club
from bayserver_core.docker.permission import Permission
from bayserver_core.docker.trouble import Trouble
from bayserver_core.docker.log import Log
from bayserver_core.docker.built_in.built_in_town_docker import BuiltInTownDocker
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.file.file_docker import FileDocker

from bayserver_core.util.string_util import StringUtil
from bayserver_core.util.http_status import HttpStatus

class BuiltInCityDocker(DockerBase, City):

    class ClubMatchInfo:
        def __init__(self):
            self.club = None
            self.script_name = None
            self.path_info = None

    class MatchInfo:
        def __init__(self):
            self.town = None
            self.club_match = None
            self.query_string = None
            self.redirect_uri = None
            self.rewritten_uri = None


    def __init__(self):
        self.towns = []
        self.default_town = None

        self.clubs = []
        self.default_club = None

        self.log_list = []
        self.permission_list = []

        self.trouble = None
        self.name = None

    def __str__(self):
        return f"City[{self.name}]"

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        self.name = elm.arg
        self.towns.sort(key=lambda x: len(x.name), reverse=True)

        for t in self.towns:
            BayLog.debug(BayMessage.get(Symbol.MSG_SETTING_UP_TOWN, t.name, t.location))

        self.default_town = BuiltInTownDocker()
        self.default_club = FileDocker()



    ######################################################
    # Implements DockerBase
    ######################################################

    def init_docker(self, dkr):
        if isinstance(dkr, Town):
            self.towns.append(dkr)
        elif isinstance(dkr, Club):
            self.clubs.append(dkr)
        elif isinstance(dkr, Log):
            self.log_list.append(dkr)
        elif isinstance(dkr, Permission):
            self.permission_list.append(dkr)
        elif isinstance(dkr, Trouble):
            self.trouble = dkr
        else:
            return False
        return True


    def enter(self, tur):
        BayLog.debug("%s City[%s] Request URI: %s", tur, self.name, tur.req.uri)

        tur.city = self
        for p in self.permission_list:
            p.tour_admitted(tur)

        match_info = self.get_town_and_club(tur.req.uri)
        if match_info is None:
            raise HttpException(HttpStatus.NOT_FOUND, tur.req.uri)

        match_info.town.tour_admitted(tur)

        if match_info.redirect_uri is not None:
            raise HttpException.moved_temp(match_info.redirect_uri)
        else:
            BayLog.debug("%s Town[%s] Club[%s]", tur, match_info.town.name, match_info.club_match.club)

            tur.req.query_string = match_info.query_string
            tur.req.script_name = match_info.club_match.script_name

            if StringUtil.is_set(match_info.club_match.club.charset):
                tur.req.charset = match_info.club_match.club.charset
                tur.res.charset = match_info.club_match.club.charset
            else:
                tur.req.charset = BayServer.harbor.charset
                tur.res.charset = BayServer.harbor.charset

            tur.req.path_info = match_info.club_match.path_info
            if StringUtil.is_set(tur.req.path_info) and match_info.club_match.club.decode_path_info:
                try:
                    tur.req.path_info = urllib.parse.unquote(tur.req.path_info, tur.req.charset)
                except BaseException as e:
                    BayLog.error_e("%s %s", tur, e)
                    tur.req.path_info = urllib.parse.unquote(tur.req.path_info, "us-ascii")

            if match_info.rewritten_uri is not None:
                tur.req.rewritten_uri = match_info.rewritten_uri  # URI is rewritten

            clb = match_info.club_match.club
            tur.town = match_info.town
            tur.club = clb
            clb.arrive(tur)

    def log(self, tur):
        for dkr in self.log_list:
            try:
                dkr.log(tur)
            except BaseException as e:
                BayLog.error_e(e)


    ######################################################
    # Private methods
    ######################################################

    def club_maches(self, club_list, rel_uri, town_name):

        cmi = BuiltInCityDocker.ClubMatchInfo()
        any_club = None

        for clb in club_list:
            if clb.file_name == "*" and clb.extension is None:
                # Ignore any match club
                any_club = clb
                break

        # search for club
        rel_script_name = ""
        for fname in rel_uri.split("/"):
            if rel_script_name != "":
                rel_script_name += "/";
            rel_script_name += fname

            for clb in club_list:
                if clb == any_club:
                    # Ignore any match club
                    continue

                if clb.matches(fname):
                    cmi.club = clb;
                    break
            else:
                continue
            break

        if cmi.club is None and any_club is not None:
            cmi.club = any_club

        if cmi.club is None:
            return None

        if town_name == "/" and rel_script_name == "":
            cmi.script_name = "/"
            cmi.path_info = None
        else:
            cmi.script_name = town_name + rel_script_name
            if len(rel_script_name) == len(rel_uri):
                cmi.path_info = None
            else:
                cmi.path_info = rel_uri[len(rel_script_name):]

        return cmi

    def get_town_and_club(self, req_uri):
        if req_uri is None:
            raise RuntimeError("Req uri is nil")

        mi = BuiltInCityDocker.MatchInfo()

        uri = req_uri
        pos = uri.find('?')
        if pos >= 0:
            mi.query_string = uri[pos + 1:]
            uri = uri[0:pos]


        for t in self.towns:
            mtype = t.matches(uri)
            if mtype == Town.MATCH_TYPE_NOT_MATCHED:
                continue


            # town matched
            mi.town = t
            if mtype == Town.MATCH_TYPE_CLOSE:
                mi.redirect_uri = uri + "/"
                if mi.query_string is not None:
                    mi.redirect_uri += mi.query_string
                return mi


            org_uri = uri
            uri = t.reroute(uri)
            if uri != org_uri:
                mi.rewritten_uri = uri

            rel = uri[len(t.name):]

            mi.club_match = self.club_maches(t.clubs, rel, t.name)
            if mi.club_match is None:
                mi.club_match = self.club_maches(self.clubs, rel, t.name)


            if mi.club_match is None:
                # check index file
                if uri.endswith("/") and not StringUtil.is_empty(t.welcome):
                    index_uri = uri + t.welcome
                    rel_uri = rel + t.welcome
                    index_location = os.path.join(t.location, rel_uri)

                    if os.path.isfile(index_location):
                        if mi.query_string is not None:
                            index_uri += "?" + mi.query_string

                        m2 = self.get_town_and_club(index_uri)
                        if m2 is not None:
                            # matched
                            m2.rewritten_uri = index_uri
                            return m2

                # default club matches
                mi.club_match = BuiltInCityDocker.ClubMatchInfo()
                mi.club_match.club = self.default_club
                mi.club_match.script_name = None
                mi.club_match.path_info = None
            return mi
        return None


