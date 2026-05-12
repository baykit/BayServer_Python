from bayserver_docker_http3.qic_command import QicCommand
from bayserver_docker_http3.qic_command_type import QicCommandType


class CmdHeader(QicCommand):

    def __init__(self, stm_id, req_headers, has_body):
        super().__init__(QicCommandType.HEADERS)
        self.stm_id = stm_id
        # req_headers is a list of (name_bytes, value_bytes) tuples as
        # surfaced by croute's H3 Event.
        self.req_headers = req_headers
        self.has_body = has_body
