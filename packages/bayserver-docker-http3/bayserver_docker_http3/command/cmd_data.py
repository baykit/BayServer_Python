from bayserver_docker_http3.qic_command import QicCommand
from bayserver_docker_http3.qic_command_type import QicCommandType


class CmdData(QicCommand):

    def __init__(self, stm_id):
        super().__init__(QicCommandType.DATA)
        self.stm_id = stm_id
