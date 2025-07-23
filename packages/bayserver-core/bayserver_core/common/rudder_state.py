import threading
import time
from typing import List, Any

from bayserver_core.agent.multiplexer.write_unit import WriteUnit
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.transporter import Transporter
from bayserver_core.rudder.rudder import Rudder


class RudderState:
    rudder: Rudder
    multiplexer: Multiplexer
    transporter: Transporter
    timeout_sec: int

    accepting: bool
    connecting: bool
    buf_size: int
    read_buf: bytes
    write_queue: List[WriteUnit]
    write_queue_lock: threading.Lock
    reading_lock: threading.Lock
    writing_lock: threading.Lock
    reading: bool
    writing: bool
    bytes_read: int
    bytes_written: int
    last_access_time: int
    finale: bool
    handshaking: bool
    addr: Any


    def __init__(self, rd: Rudder, tp: Transporter=None, timeout_sec: int=0):
        self.rudder = rd
        self.transporter = tp
        self.timeout_sec = timeout_sec
        self.closed = False

        if tp is not None:
            self.buf_size = tp.get_read_buffer()
            self.handshaking = tp.is_secure()
        else:
            self.buf_size = 8192
            self.handshaking = False

        self.accepting = False
        self.connecting = False
        self.write_queue = []
        self.write_queue_lock = threading.Lock()
        self.reading_lock = threading.Lock()
        self.writing_lock = threading.Lock()
        self.reading = False
        self.writing = False
        self.bytes_read = 0
        self.bytes_written = 0
        self.last_access_time = time.time()
        self.finale = False
        self.read_buf = None
        self.addr = None


    def __str__(self):
        return f"st(rd=#{self.rudder} mpx=#{self.multiplexer} tp=#{self.transporter})"

    def access(self):
        self.last_access_time = time.time()

    def end(self):
        self.finale = True