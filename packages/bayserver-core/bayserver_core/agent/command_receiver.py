from bayserver_core.bay_log import BayLog

from bayserver_core.agent import grand_agent as ga

from bayserver_core.util.io_util import IOUtil

#
# CommandReceiver receives commands from GrandAgentMonitor
#
class CommandReceiver:
    def __init__(self, agent, com_ch):
        self.agent = agent
        self.communication_channel = com_ch
        self.aborted = False

    def __str__(self):
        return f"ComReceiver#{self.agent.agent_id}"

    def on_pipe_readable(self):
        try:
            cmd = IOUtil.recv_int32(self.communication_channel)
            if cmd is None:
                BayLog.debug("%s pipe closed: %s", self, self.communication_channel)
                self.agent.abort()
            else:
                BayLog.debug("%s receive command %d pipe=%s", self, cmd, self.communication_channel)
                if cmd == ga.GrandAgent.CMD_RELOAD_CERT:
                    self.agent.reload_cert()
                elif cmd == ga.GrandAgent.CMD_MEM_USAGE:
                    self.agent.print_usage()
                elif cmd == ga.GrandAgent.CMD_SHUTDOWN:
                    self.agent.shutdown()
                    self.aborted = True
                elif cmd == ga.GrandAgent.CMD_ABORT:
                    IOUtil.send_int32(self.communication_channel, ga.GrandAgent.CMD_OK)
                    self.agent.abort()
                    return
                else:
                    BayLog.error("Unknown command: %d", cmd)

                IOUtil.send_int32(self.communication_channel, ga.GrandAgent.CMD_OK)

        except BaseException as e:
            BayLog.error_e(e)
            BayLog.error_e(e, "%s Command thread aborted(end)", self)
            self.close()

    def end(self):
        BayLog.debug("%s end", self)
        try:
            IOUtil.send_int32(self.communication_channel, ga.GrandAgent.CMD_CLOSE)
        except BaseException as e:
            BayLog.error_e(e, "%s Write error", self.agent)
        self.close()

    def close(self):
        self.communication_channel.close()
