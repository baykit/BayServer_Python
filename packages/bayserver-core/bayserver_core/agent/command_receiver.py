from typing import Any

from bayserver_core.agent.monitor.grand_agent_monitor import GrandAgentMonitor
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.bay_log import BayLog

from bayserver_core.agent import grand_agent as ga
from bayserver_core.common.transporter import Transporter
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.ship.ship import Ship
from bayserver_core.sink import Sink

from bayserver_core.util.io_util import IOUtil

#
# CommandReceiver receives commands from GrandAgentMonitor
#
class CommandReceiver(Ship):

    closed: bool

    def init(self, agent_id: int, rd: Rudder, tp: Transporter):
        super().init(agent_id, rd, tp)
        self.closed = False

    def __str__(self):
        return f"ComReceiver#{self.agent_id}"

    ######################################################
    # implements Ship
    ######################################################

    def notify_handshake_done(self, proto: str):
        raise Sink()

    def notify_connect(self):
        raise Sink()

    def notify_read(self, buf: bytes, adr: Any):
        BayLog.debug("%s notify_read", self)
        cmd = GrandAgentMonitor.buffer_to_int(buf)
        self.on_read_command(cmd)
        return NextSocketAction.CONTINUE

    def notify_eof(self):
        BayLog.debug("%s notify_eof", self)
        return NextSocketAction.CLOSE

    def notify_error(self, e: Exception):
        BayLog.error(e)

    def notify_protocol_error(self, e: ProtocolException):
        raise Sink()

    def notify_close(self):
        pass

    def check_timeout(self, duration_sec: int):
        return False


    ######################################################
    # Custom methods
    ######################################################

    def on_read_command(self, cmd):
        agt = ga.GrandAgent.get(self.agent_id)

        try:
            if cmd is None:
                BayLog.debug("%s pipe closed: %s", self, self.rudder)
                agt.abort_agent()
            else:
                BayLog.debug("%s receive command %d pipe=%s", self, cmd, self.rudder)
                if cmd == ga.GrandAgent.CMD_RELOAD_CERT:
                    agt.reload_cert()
                elif cmd == ga.GrandAgent.CMD_MEM_USAGE:
                    agt.print_usage()
                elif cmd == ga.GrandAgent.CMD_SHUTDOWN:
                    agt.req_shutdown()
                elif cmd == ga.GrandAgent.CMD_ABORT:
                    IOUtil.send_int32(self.rudder.key(), ga.GrandAgent.CMD_OK)
                    agt.abort_agent()
                    return
                else:
                    BayLog.error("Unknown command: %d", cmd)

                self.send_command_to_monitor(agt, ga.GrandAgent.CMD_OK, False)

        except BaseException as e:
            BayLog.error_e(e)
            BayLog.error_e(e, "%s Command thread aborted(end)", self)
            self.close()

    def send_command_to_monitor(self, agt, cmd: int, sync: bool):
        buf = GrandAgentMonitor.int_to_buffer(cmd)

    def end(self):
        BayLog.debug("%s send end to monitor", self)
        try:
            self.send_command_to_monitor(None, ga.GrandAgent.CMD_CLOSE, True)
        except BaseException as e:
            BayLog.error_e(e, "%s Write error", self.agent)
        self.close()

    def close(self):
        if self.closed:
            return

        self.rudder.close()
