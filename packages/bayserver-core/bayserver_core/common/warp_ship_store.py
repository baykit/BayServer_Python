import threading
from typing import List, AnyStr, Optional

from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink

from bayserver_core.common.warp_ship import WarpShip
from bayserver_core.util.object_store import ObjectStore
from bayserver_core.util.string_util import StringUtil

class WarpShipStore(ObjectStore):

    keep_list: List[WarpShip]
    busy_list: List[WarpShip]
    lock: threading.RLock
    max_ships: int
    factory: any

    def __init__(self, max_ships):
        super().__init__()
        self.keep_list = []
        self.busy_list = []
        self.lock = threading.RLock()
        self.max_ships = max_ships
        self.factory = lambda : WarpShip()

    def __str__(self):
        return "warp_ship_store"


    def rent(self) -> Optional[WarpShip]:

        with self.lock:
            if 0 < self.max_ships <= self.count():
                return None

            wsip = None
            if len(self.keep_list) > 0:
                for i in reversed(range(len(self.keep_list))):
                    if not self.keep_list[i].rudder.closed():
                        wsip = self.keep_list[i]
                        self.keep_list.pop(i)
                        break

            if wsip is None:
                BayLog.debug("rent from Object Store")
                wsip = super().rent()
                if wsip is None:
                    return None

            self.busy_list.append(wsip)

            BayLog.trace(" rent keepList=%s busyList=%s", self.keep_list, self.busy_list)
            return wsip

    def keep(self, wsip):
        with self.lock:
            BayLog.trace("keep: before keepList=%s busyList=%s", self.keep_list, self.busy_list)

            if not wsip in self.busy_list:
                BayLog.error("%s not in busy list", wsip)
            else:
                self.busy_list.remove(wsip)

            self.keep_list.append(wsip)

            BayLog.trace("keep: after keepList=%s busyList=%s", self.keep_list, self.busy_list)

    def Return(self, wsip, reuse=False):
        with self.lock:
            BayLog.trace("Return: before keepList=%s busyList=%s", self.keep_list, self.busy_list)

            removed_from_keep = False
            if wsip in self.keep_list:
                self.keep_list.remove(wsip)
                removed_from_keep = True

            removed_from_busy = False
            if wsip in self.busy_list:
                self.busy_list.remove(wsip)
                removed_from_busy = True

            if not removed_from_keep and not removed_from_busy:
                BayLog.error("%s not in both keep list and busy list", wsip)

            super().Return(wsip, reuse)

            BayLog.trace("Return: after keepList=%s busyList=%s", self.keep_list, self.busy_list)

    def count(self):
        return len(self.keep_list) + len(self.busy_list)

    def print_usage(self, indent):
        BayLog.info("%sWarpShipStore Usage:", StringUtil.indent(indent))
        BayLog.info("%skeepList: %d", StringUtil.indent(indent + 1), len(self.keep_list))
        if BayLog.debug_mode():
            for obj in self.busy_list:
                BayLog.debug("%s%s", StringUtil.indent(indent + 1), obj)
        BayLog.info("%sbusyList: %d", StringUtil.indent(indent + 1), len(self.busy_list))
        if BayLog.debug_mode():
            for obj in self.keep_list:
                BayLog.debug("%s%s", StringUtil.indent(indent + 1), obj)
        super().print_usage(indent)