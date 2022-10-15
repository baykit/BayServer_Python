import os

from baykit.bayserver.bay_log import BayLog
from baykit.bayserver.agent import grand_agent as ga
from baykit.bayserver.util.io_util import IOUtil

class GrandAgentMonitor:

    def __init__(self, agt_id, anchorable, send_pipe, recv_pipe):
        self.agent_id = agt_id
        self.anchorable = anchorable
        self.send_pipe = send_pipe
        self.recv_pipe = recv_pipe

    def __str__(self):
        return f"Monitor#{self.agent_id}"

    def on_readable(self):
        try:
            while True:
              res = IOUtil.read_int32(self.recv_pipe[0])
              if res is None or res == ga.GrandAgent.CMD_CLOSE:
                BayLog.debug("%s read Close", self)
                ga.GrandAgent.agent_aborted(self.agent_id, self.anchorable)
              else:
                BayLog.debug("%s read: %d", self, res)
        except BlockingIOError as e:
            BayLog.debug("%s no data", self)

    def shutdown(self):
        BayLog.debug("%s send shutdown command", self)
        self.send(ga.GrandAgent.CMD_SHUTDOWN)

    def abort(self):
        BayLog.debug("%s Send abort command", self)
        self.send(ga.GrandAgent.CMD_ABORT)

    def reload_cert(self):
        BayLog.debug("%s Send reload command", self)
        self.send(ga.GrandAgent.CMD_RELOAD_CERT)

    def print_usage(self):
        BayLog.debug("%s Send mem_usage command", self)
        self.send(ga.GrandAgent.CMD_MEM_USAGE)

    def join(self):
        self.waiter.join()

    def send(self, cmd):
        BayLog.debug("%s send command %s pipe=%s", self, cmd, self.send_pipe[1])
        IOUtil.write_int32(self.send_pipe[1], cmd)

    def close(self):
        try:
            os.close(self.send_pipe[0])
        except IOError as e:
            BayLog.debug_e(e, "Close pipe error")

        os.close(self.send_pipe[1])
        os.close(self.recv_pipe[0])

        try:
            os.close(self.recv_pipe[1])
        except IOError as e:
            BayLog.debug_e(e, "Close pipe error")
