from bayserver_core.util.reusable import Reusable
from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.util.object_factory import ObjectFactory
from bayserver_core.util.string_util import StringUtil

class ObjectStore(Reusable):

    def __init__(self, factory=None):
        self.free_list = []
        self.active_list = []
        self.factory = factory

    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        if len(self.active_list) > 0:
            BayLog.error("BUG?: There are %d active objects: %s",  len(self.active_list), self.active_list)

            # for security
            self.free_list.clear()
            self.active_list.clear()

    ######################################################
    # Other methods
    ######################################################

    def rent(self):
        if len(self.free_list) == 0:
            if isinstance(self.factory, ObjectFactory):
                obj = self.factory.create_object()
            else:
                # lambda
                obj = self.factory()
        else:
            obj = self.free_list.pop()

        if obj is None:
            raise Sink()

        self.active_list.append(obj)

        return obj

    def Return(self, obj, reuse=True):
        if obj in self.free_list:
            raise Sink("This object already returned: %s", obj)

        if obj not in self.active_list:
            raise Sink("This object is not active: %s", obj)

        self.active_list.remove(obj)

        if reuse:
            self.free_list.append(obj)

        obj.reset()

    def print_usage(self, indent):
        BayLog.info("%sfree list: %d", StringUtil.indent(indent), len(self.free_list));
        BayLog.info("%sactive list: %d", StringUtil.indent(indent), len(self.active_list));
        if BayLog.debug_mode():
            for obj in self.active_list:
                BayLog.debug("%s%s", StringUtil.indent(indent + 1), obj)

