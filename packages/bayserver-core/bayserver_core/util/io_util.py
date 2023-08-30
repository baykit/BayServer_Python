import os
import socket

from bayserver_core.bay_log import BayLog
from bayserver_core.bay_message import BayMessage
from bayserver_core.symbol import Symbol

class IOUtil:
    @classmethod
    def read_int32(cls, io):
        data = os.read(io, 4)
        return data[0] << 24 | (data[1] << 16 & 0xFF0000) | (data[2] << 8 & 0xFF00) | (data[3] & 0xFF)


    @classmethod
    def write_int32(cls, io, i):
        data = bytearray(4)
        data[0] = i >> 24
        data[1] = i >> 16 & 0xFF
        data[2] = i >> 8 & 0xFF
        data[3] = i & 0xFF
        os.write(io, data)

    @classmethod
    def recv_int32(cls, skt):
        data = skt.recv(4)
        if len(data) == 0:
            return None
        elif len(data) < 4:
            raise IOError("Not enough bytes: len=%d", len(data))
        else:
            return data[0] << 24 | (data[1] << 16 & 0xFF0000) | (data[2] << 8 & 0xFF00) | (data[3] & 0xFF)


    @classmethod
    def send_int32(cls, skt, i):
        data = bytearray(4)
        data[0] = i >> 24
        data[1] = i >> 16 & 0xFF
        data[2] = i >> 8 & 0xFF
        data[3] = i & 0xFF
        skt.send(data)

    @classmethod
    def open_local_pipe(cls):
        # Dynamic and/or Private Ports (49152-65535)
        # https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml
        DYNAMIC_PORTS_START = 49152
        for port in range(DYNAMIC_PORTS_START, 65535 + 1):
            try:
                return cls.open_local_pipe_by_port(port)
            except BaseException as e:
                continue

        return None



    @classmethod
    def open_local_pipe_by_port(cls, port_num):
        BayLog.debug(BayMessage.get(Symbol.MSG_OPENING_LOCAL_PORT, port_num))
        localhost = "127.0.0.1"

        server_skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_skt.bind((localhost, port_num))
        server_skt.listen(0)

        source_skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        source_skt.connect((localhost, port_num))
        sink_skt, addr = server_skt.accept()
        BayLog.debug(BayMessage.get(Symbol.MSG_CLOSING_LOCAL_PORT, port_num))
        server_skt.close()

        source_skt.setblocking(False)
        sink_skt.setblocking(False)
        return sink_skt, source_skt






    @classmethod
    def get_sock_recv_buf_size(cls, skt):
        return int(skt.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))


    @classmethod
    def set_non_blocking(cls, fd):
        import fcntl
        fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)