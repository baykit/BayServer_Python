import os
import socket

from baykit.bayserver import bayserver as bs
from baykit.bayserver.bay_log import BayLog

from baykit.bayserver.bcf.bcf_parser import BcfParser
from baykit.bayserver.bcf.bcf_element import BcfElement

from baykit.bayserver.agent.signal.signal_agent import SignalAgent
from baykit.bayserver.docker.built_in.built_in_harbor_docker import BuiltInHarborDocker


class SignalSender:

    def __init__(self):
        self.bay_port = BuiltInHarborDocker.DEFAULT_CONTROL_PORT
        self.pid_file = bs.BayServer.get_location(BuiltInHarborDocker.DEFAULT_PID_FILE);

    #
    # Send running BayServer a command
    #
    def send_command(self, cmd):
        self.parse_bay_port(bs.BayServer.bserv_plan)

        if self.bay_port < 0:
            pid = self.read_pid_file()
            sig = SignalAgent.get_signal_from_command(cmd)
            BayLog.info("Send command to running BayServer: pid=%d sig=%d", pid, sig)
            if sig is None:
                raise Exception("Invalid command: " + cmd)
            else:
                os.kill(pid, sig)

        else:
            BayLog.info("Send command to running BayServer: cmd=%s port=%d", cmd, self.bay_port)
            self.send("localhost", self.bay_port, cmd)

    #
    # Parse plan file and get port number of SignalAgent
    #
    def parse_bay_port(self, plan):
        p = BcfParser()
        doc = p.parse(plan)
        for elm in doc.content_list:
            if isinstance(elm, BcfElement):
                if elm.name.lower() == "harbor":
                    for kv in elm.content_list:
                        if kv.key.lower() == "controlport":
                            self.bay_port = int(kv.value)
                        elif kv.key.lower() == "pidfile":
                            self.pid_file = kv.value

    def send(self, host, port, cmd):
        try:
            skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            skt.connect((host, port))
            f = skt.makefile("rw")
            f.write(f"{cmd}\n")
            f.flush()
            line = f.readline()

        except BaseException as e:
            BayLog.error_e(e)

        finally:
            skt.close()

    def read_pid_file(self):
        with open(self.pid_file, "r") as f:
            return int(f.readline())