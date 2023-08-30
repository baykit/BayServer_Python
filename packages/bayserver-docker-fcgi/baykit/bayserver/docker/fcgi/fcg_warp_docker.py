from baykit.bayserver.bay_log import BayLog

from baykit.bayserver.agent.transporter.plain_transporter import PlainTransporter
from baykit.bayserver.protocol.packet_store import PacketStore
from baykit.bayserver.protocol.protocol_handler_store import ProtocolHandlerStore
from baykit.bayserver.util.io_util import IOUtil

from baykit.bayserver.docker.warp.warp_docker import WarpDocker

from baykit.bayserver.docker.fcgi.fcg_docker import FcgDocker
from baykit.bayserver.docker.fcgi.fcg_packet_factory import FcgPacketFactory
from baykit.bayserver.docker.fcgi.fcg_warp_handler import FcgWarpHandler

class FcgWarpDocker(WarpDocker, FcgDocker):

    def __init__(self):
        super().__init__()
        self.script_base = None
        self.doc_root = None


    ######################################################
    # Implements Docker
    ######################################################
    def init(self, elm, parent):
        super().init(elm, parent)

        if self.script_base is None:
            BayLog.warn("FCGI: docRoot is not specified")

    ######################################################
    # Implements DockerBase
    ######################################################

    def init_key_val(self, kv):
        key = kv.key.lower()
        if key == "scritbase":
            self.script_base = kv.value
        elif key == "docroot":
            self.doc_root = kv.value
        else:
            return super().init_key_val(kv)

        return True

    ######################################################
    # Implements WarpDocker
    ######################################################
    def secure(self):
        return False

    ######################################################
    # Implements WarpDockerBase
    ######################################################
    def protocol(self):
        return FcgDocker.PROTO_NAME

    def new_transporter(self, agt, skt):
        return PlainTransporter(False, IOUtil.get_sock_recv_buf_size(skt))

    ######################################################
    # Class initializer
    ######################################################
    PacketStore.register_protocol(
        FcgDocker.PROTO_NAME,
        FcgPacketFactory())
    ProtocolHandlerStore.register_protocol(
        FcgDocker.PROTO_NAME,
        False,
        FcgWarpHandler.WarpProtocolHandlerFactory())
