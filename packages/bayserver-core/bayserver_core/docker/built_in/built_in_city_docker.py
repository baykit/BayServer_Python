import os.path
import urllib.parse
import traceback
from typing import List

from bayserver_core.bayserver import BayServer
from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.http_exception import HttpException
from bayserver_core.symbol import Symbol

from bayserver_core.common.barges import Barges
from bayserver_core.docker.barge import Barge
from bayserver_core.docker.city import City
from bayserver_core.docker.town import Town
from bayserver_core.docker.club import Club
from bayserver_core.docker.permission import Permission
from bayserver_core.docker.trouble import Trouble
from bayserver_core.docker.log import Log
from bayserver_core.docker.built_in.built_in_town_docker import BuiltInTownDocker
from bayserver_core.docker.base.docker_base import DockerBase
from bayserver_core.docker.file.file_docker import FileDocker
from bayserver_core.tour.tour import Tour

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
        self.barges = Barges()

        self.trouble = None
        self._name = None

    def __str__(self):
        return f"City[{self._name}]"

    ######################################################
    # Implements Docker
    ######################################################

    def init(self, elm, parent):
        super().init(elm, parent)

        self._name = elm.arg
        self.towns.sort(key=lambda x: len(x.name()), reverse=True)

        for t in self.towns:
            BayLog.debug(BayMessage.get(Symbol.MSG_SETTING_UP_TOWN, t.name(), t.location))

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
        elif isinstance(dkr, Barge):
            self.barges.add(dkr)
        else:
            return False
        return True


    def enter(self, tur):
        BayLog.debug("%s City[%s] Request URI: %s", tur, self._name, tur.req.uri)

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
            BayLog.debug("%s Town[%s] Club[%s]", tur, match_info.town.name(), match_info.club_match.club)

            tur.req.query_string = match_info.query_string
            tur.req.script_name = match_info.club_match.script_name

            if StringUtil.is_set(match_info.club_match.club.charset()):
                tur.req._charset = match_info.club_match.club.charset()
                tur.res._charset = match_info.club_match.club.charset()
            else:
                tur.req._charset = BayServer.harbor.charset()
                tur.res._charset = BayServer.harbor.charset()

            tur.req.path_info = match_info.club_match.path_info
            if StringUtil.is_set(tur.req.path_info) and match_info.club_match.club.decode_path_info:
                try:
                    tur.req.path_info = urllib.parse.unquote(tur.req.path_info, tur.req._charset)
                except BaseException as e:
                    BayLog.error_e(e,  traceback.format_stack(), "%s %s", tur)
                    tur.req.path_info = urllib.parse.unquote(tur.req.path_info, "us-ascii")

            if match_info.rewritten_uri is not None:
                tur.req.rewritten_uri = match_info.rewritten_uri  # URI is rewritten

            clb = match_info.club_match.club
            tur.town = match_info.town
            tur.club = clb

            barge = self._find_barge_for(tur, match_info.town)
            if barge is not None:
                cgo, rd = barge.get_cargo(tur)

                if rd is not None:
                    # Cargo is loading; wait until it is loaded.
                    self._wait_for_cargo(tur, rd, cgo, clb)
                    return
                elif cgo.on_barge():
                    # Cargo is ready (on cache).
                    self._serve_from_cargo(tur, cgo)
                    return
                else:
                    tur.cargo = cgo

            clb.arrive(tur)

    def _wait_for_cargo(self, tur, rd, cgo, clb):
        # Imported lazily to avoid bootstrap circular imports.
        from bayserver_core.agent.grand_agent import GrandAgent
        from bayserver_core.agent.multiplexer.plain_transporter import PlainTransporter
        from bayserver_core.common.rudder_state import RudderState
        from bayserver_core.docker.built_in.wait_cargo_ship import WaitCargoShip

        agt = GrandAgent.get(tur.ship.agent_id)
        wait_ship = WaitCargoShip()
        tp = PlainTransporter(agt.spider_multiplexer, wait_ship, True, 8192, False)
        wait_ship.init(rd, tp, tur, cgo, clb)
        agt.spider_multiplexer.add_rudder_state(rd, RudderState(rd, tp))
        agt.spider_multiplexer.req_read(rd)

    def _serve_from_cargo(self, tur, cgo):
        from bayserver_core.tour.req_content_handler import ReqContentHandler

        class _CargoReqContentHandler(ReqContentHandler):
            def on_read_req_content(self, t, buf, start, length, lis):
                pass

            def on_end_req_content(self, t):
                cgo.headers().copy_to(t.res.headers)
                t.res.send_res_headers(Tour.TOUR_ID_NOCHECK)
                t.res.set_res_consume_listener(lambda length, resume: None)
                t.res.send_res_content(Tour.TOUR_ID_NOCHECK, cgo.content(), 0, cgo.length())
                t.res.end_res_content(Tour.TOUR_ID_NOCHECK)

            def on_abort_req(self, t):
                return False

        tur.req.set_content_handler(_CargoReqContentHandler())

    def _find_barge_for(self, tur, twn):
        b = twn.find_barge(tur.req.uri)
        if b is None:
            b = self.barges.find_barge(tur.req.uri)
            if b is None:
                b = BayServer.harbor.find_barge(tur.req.uri)
        return b

    def log(self, tur):
        for dkr in self.log_list:
            try:
                dkr.log(tur)
            except BaseException as e:
                BayLog.error_e(e, traceback.format_stack())

    ######################################################
    # Implements City
    ######################################################

    def name(self) -> str:
        return self._name

    def clubs(self) -> List[Club]:
        return self.clubs

    def towns(self) -> List[Town]:
        return self.towns

    def get_trouble(self) -> Trouble:
        return self.trouble

    def find_barge(self, path):
        # Java BuiltInCityDocker.findBarge always returns null; lookup
        # happens via the city/town/harbor chain inside enter().
        return None


    ######################################################
    # Private methods
    ######################################################

    def club_maches(self, club_list, rel_uri, town_name):

        cmi = BuiltInCityDocker.ClubMatchInfo()
        any_club = None

        for clb in club_list:
            if clb.file_name() == "*" and clb.extension() is None:
                # Ignore any match club
                any_club = clb
                break

        # search for club
        rel_script_name = ""
        for fname in rel_uri.split("/"):
            if rel_script_name != "":
                rel_script_name += "/"
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

            rel = uri[len(t.name()):]

            mi.club_match = self.club_maches(t.clubs, rel, t.name())
            if mi.club_match is None:
                mi.club_match = self.club_maches(self.clubs, rel, t.name())


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


