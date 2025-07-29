import errno
import os
import selectors
import socket
import ssl
import threading
import traceback
from selectors import SelectorKey
from typing import List

from bayserver_core import bayserver as bs
from bayserver_core.agent import grand_agent as ga
from bayserver_core.agent.multiplexer.multiplexer_base import MultiplexerBase
from bayserver_core.agent.multiplexer.write_unit import WriteUnit
from bayserver_core.agent.timer_handler import TimerHandler
from bayserver_core.bay_log import BayLog
from bayserver_core.common.multiplexer import Multiplexer
from bayserver_core.common.recipient import Recipient
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.rudder.udp_socket_rudder import UdpSocketRudder
from bayserver_core.sink import Sink
from bayserver_core.util.exception_util import ExceptionUtil
from bayserver_core.util.internet_address import InternetAddress
from bayserver_core.util.io_util import IOUtil
from bayserver_core.util.sys_util import SysUtil


class SpiderMultiplexer(MultiplexerBase, TimerHandler, Multiplexer, Recipient):

    class ChannelOperation:
        rudder: Rudder
        op: int
        to_connect: bool

        def __init__(self, rudder: Rudder, op: int, to_connect: bool):
            self.rudder = rudder
            self.op = op
            self.to_connect = to_connect

    anchorable: bool
    selector: selectors.BaseSelector
    operations: List[ChannelOperation]
    operations_lock: threading.Lock
    select_wakeup_pipe: List[socket.socket]

    def __init__(self, agt: "ga.GrandAgent", anchorable: bool):
        MultiplexerBase.__init__(self, agt)
        self.anchorable = anchorable
        self.selector = selectors.DefaultSelector()
        if (hasattr(selectors, 'KqueueSelector') and
                isinstance(self.selector, selectors.KqueueSelector)):

            # On macOS, since we cannot detect the EOF status using KqueueSelector for files,
            # we instead use PollSelector.
            try:
                self.selector = selectors.PollSelector()
            except BaseException as e:
                BayLog.warn_e(e, traceback.format_stack(), "Cannot create PollSelector")

                self.selector = selectors.SelectSelector()

        self.operations = []
        self.operations_lock = threading.Lock()

        pair = socket.socketpair()
        pair[0].setblocking(False)
        pair[1].setblocking(False)
        self.select_wakeup_pipe = [pair[0], pair[1]]
        self.selector.register(self.select_wakeup_pipe[0], selectors.EVENT_READ)

        self.agent.add_timer_handler(self)

    def __str__(self):
        return f"SpdMpx[{self.agent}]"


    ######################################################
    # Implements Transporter
    ######################################################

    def req_accept(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        self.selector.register(rd.key(), selectors.EVENT_READ)
        st.accepting = True

    def req_connect(self, rd: Rudder, adr: InternetAddress) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqConnect adr=%s rd=%s chState=%s", self.agent, adr, rd, st)

        rd.set_non_blocking()

        err = rd.key().connect_ex(adr)
        if SysUtil.run_on_windows():
            ok = err == 10035
        else:
            ok = err == errno.EINPROGRESS
        ok |= (err == 0)

        if not ok:
            BayLog.error("%s connect error: adr=%s %s(%d)", self, adr, os.strerror(err), err)
            raise IOError("Connect failed: " + str(adr))

        st.is_connecting = True

        self._add_operation(rd, selectors.EVENT_WRITE, True)

    def req_read(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqRead st=%s", self, st);

        self._add_operation(rd, selectors.EVENT_READ)

        if st is not None:
            st.access()

    def req_write(self, rd: Rudder, buf: bytearray, adr: InternetAddress, tag: object, lis) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqWrite st=%s tag=%s len=%d", self, st, tag, len(buf))

        if st is None or st.closed:
            BayLog.warn("%s Rudder is closed: %s", self, rd)
            lis()
            return

        unt = WriteUnit(buf, adr, tag, lis)
        with st.write_queue_lock:
            st.write_queue.append(unt)

        self._add_operation(rd, selectors.EVENT_WRITE)

        st.access()

    def req_end(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        if st is None:
            return

        st.end()
        st.access()


    def req_close(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqClose st=%s", self, st)

        if st is None:
            BayLog.warn("%s channel state not found: %s", self.agent, rd)
            return

        self.close_rudder(st.rudder)

        self.agent.send_closed_letter(st, False)

        st.access()

    def shutdown(self) -> None:
        self.wakeup()

    def is_non_blocking(self) -> bool:
        return True

    def use_async_api(self) -> bool:
        return False

    def cancel_read(self, st: RudderState) -> None:
        if not st.rudder.closed():
            self.selector.unregister(st.rudder.key())

    def cancel_write(self, st: RudderState) -> None:
        if not st.rudder.closed():
            key = self.selector.get_key(st.rudder.key())
            op = key.events & ~selectors.EVENT_WRITE

            if op != selectors.EVENT_READ:
                self.selector.unregister(st.rudder.key())
            else:
                self.selector.modify(st.rudder.key(), op)

    def next_accept(self, st: RudderState) -> None:
        pass

    def next_read(self, st: RudderState) -> None:
        pass

    def next_write(self, st: RudderState) -> None:
        pass

    def close_rudder(self, rd: Rudder) -> None:
        if not rd.closed():
            try:
                self.selector.unregister(rd.key())
            except KeyError:
                BayLog.error("%s Rudder is not registered: %s", self.agent, rd)
        MultiplexerBase.close_rudder(self, rd)

    def on_busy(self) -> None:
        BayLog.debug("%s onBusy", self.agent)
        for rd in bs.BayServer.anchorable_port_map.keys():
            self.selector.unregister(rd.key())
            st = self.get_rudder_state(rd)
            st.accepting = False

    def on_free(self) -> None:
        BayLog.debug("%s onFree aborted=%s", self.agent, self.agent.aborted)
        if self.agent.aborted:
            return

        for rd in bs.BayServer.anchorable_port_map.keys():
            self.req_accept(rd)


    ######################################################
    # Implements TimerHandler
    ######################################################
    def on_timer(self) -> None:
        self.close_timeout_sockets()


    ######################################################
    # Implements Recipient
    ######################################################

    def receive(self, wait: bool) -> bool:
        if not wait:
            selkeys = self.selector.select(0)
        else:
            selkeys = self.selector.select(ga.GrandAgent.SELECT_TIMEOUT_SEC)

        self._register_channel_ops()

        for key, events in selkeys:
            if key.fd == self.select_wakeup_pipe[0].fileno():
                # Waked up by req_*
                self._on_waked_up()
            else:
                self._handle_channel(key, events)

    def wakeup(self) -> None:
        BayLog.trace("%s WakeUp", self)
        try:
            IOUtil.send_int32(self.select_wakeup_pipe[1], 0)
        except BlockingIOError as e:
            BayLog.warn("%s: wakeup failed: %s", self, e)
            pass

    ######################################################
    # Private functions
    ######################################################

    def _add_operation(self, rd: Rudder, op: int, to_connect=False) -> None:
        with self.operations_lock:
            found = False
            for rd_op in self.operations:
                if rd_op.rudder == rd:
                    rd_op.op |= op
                    rd_op.to_connect = rd_op.to_connect or to_connect
                    found = True
                    BayLog.debug("%s Update operation: %s ch=%s", self, self.op_mode(rd_op.op), rd_op.rudder)

            if not found:
                BayLog.debug("%s New operation: %s ch=%s", self, self.op_mode(op), rd)
                self.operations.append(self.ChannelOperation(rd, op, to_connect))

        self.wakeup()


    def _register_channel_ops(self) -> int:
        if len(self.operations) == 0:
            return 0

        #BayLog.info("%s register op list: %s", self, self.operations)
        with self.operations_lock:
            nch = len(self.operations)
            for ch_op in self.operations:
                st = self.get_rudder_state(ch_op.rudder)
                if st is None:
                    BayLog.debug("%s Try to register closed socket (Ignore)", self)
                    continue

                fileobj = ch_op.rudder.key()
                try:
                    BayLog.debug("%s register op=%s ch=%s chState=%s", self, SpiderMultiplexer.op_mode(ch_op.op), ch_op.rudder, st)
                    try:
                        key = self.selector.get_key(fileobj)
                        op = key.events
                        new_op = op | ch_op.op
                        BayLog.trace("%s Already registered op=%s update to %s", self, SpiderMultiplexer.op_mode(op), SpiderMultiplexer.op_mode(new_op))
                        self.selector.modify(fileobj, new_op)
                    except KeyError:
                        # channel is not registered in selector
                        BayLog.trace("%s Not registered", self)
                        self.selector.register(fileobj, ch_op.op)

                    if ch_op.to_connect:
                        if st is None:
                            BayLog.warn("%s register connect but ChannelState is null", self)
                        else:
                            st.connecting = True

                except BaseException as e:
                    cst = self.get_rudder_state(ch_op.rudder)
                    BayLog.error_e(e, traceback.format_stack(), "%s Cannot register operation: %s", self, st.rudder)

            self.operations.clear()
            return nch


    def _handle_channel(self, key: SelectorKey, events: int) -> None:

        ch = key.fileobj
        #BayLog.trace("%s Handle channel: readable=%s writable=%s fd=%s",
        #             self.agent, events & selectors.EVENT_READ, events & selectors.EVENT_WRITE, ch)

        st = self._find_rudder_state_by_key(ch)
        if st is None:
            BayLog.error("Channel state is not registered: ch=%s", ch)
            try:
                self.selector.unregister(ch)
            except ValueError as e:
                BayLog.debug("%s Unregister error (Ignore): %s", self, e)
            return

        BayLog.debug("%s Handle channel: chState=%s readable=%s writable=%s connecting=%s",
                     self.agent, st, events & selectors.EVENT_READ, events & selectors.EVENT_WRITE,
                     st.connecting)

        try:

            if st.connecting:

                self._on_connectable(st)
                st.connecting = False

                # "Write-OP Off"
                key = self.selector.get_key(ch)
                op = key.events & ~selectors.EVENT_WRITE
                if op != selectors.EVENT_READ:
                    BayLog.debug("%s Unregister channel (Write Off) chState=%s", self.agent, st)
                    self.selector.unregister(ch)
                else:
                    self.selector.modify(ch, op)

            elif st.accepting:
                self._on_acceptable(st)

            else:
                if events & selectors.EVENT_READ != 0:
                    self._on_readable(st)

                if events & selectors.EVENT_WRITE != 0:
                    self._on_writable(st)

        except Sink as e:
            raise e

        except BaseException as e:
            if isinstance(e, EOFError):
                BayLog.debug("%s Socket closed by peer: skt=%s", self, ch)
            elif isinstance(e, OSError):
                BayLog.debug("%s O/S error: %s (skt=%s)", self, ExceptionUtil.message(e), ch)
            else:
                BayLog.debug("%s SSL error: %s (skt=%s)", self, ExceptionUtil.message(e), ch)
                raise e

            # Cannot handle Exception anymore
            BayLog.error_e(e, traceback.format_stack())
            self.agent.send_error_letter(st, e, traceback.format_stack(), False)

        st.access()

    def _on_acceptable(self, st: RudderState) -> None:
        #BayLog.debug("%s on_acceptable", self.agent)

        try:
            client_skt, addr = st.rudder.key().accept()
        except BlockingIOError as e:
            BayLog.debug("%s Error:%s (Maybe another agent caught client socket)", self.agent, e)
            return

        BayLog.debug("%s Accepted: skt=%s", self.agent, client_skt.fileno())
        client_rd = SocketRudder(client_skt)
        client_rd.set_non_blocking()

        self.agent.send_accepted_letter(st, client_rd, False)

    def _on_connectable(self, st: RudderState) -> None:
        BayLog.debug("%s onConnectable (^o^)/: rd=%s", self, st.rudder)

        # check connection by sending 0 bytes data.
        try:
            st.rudder.key().send(b"")
        except ssl.SSLWantReadError:
            # Not handshaked (OK)
            pass
        except IOError as e:
            BayLog.error_e(e, traceback.format_stack(), "Connect failed: %s", e)
            self.agent.send_error_letter(st, e, traceback.format_stack(), False)

        return self.agent.send_connected_letter(st, False)

    def _on_readable(self, st: RudderState) -> None:

        try:
            if st.handshaking:
                try:
                    st.rudder.key().do_handshake()
                    BayLog.debug("%s Handshake done (rd=%s)", self, st.rudder)
                    proto = st.rudder.key().selected_alpn_protocol()
                    #self.get_transporter(st.rudder).notify_handshake_done(proto)
                    st.handshaking = False
                except ssl.SSLWantReadError:
                    BayLog.debug("%s Need to read more: rd=%s", self, st.rudder)
                    return


            try:
                if isinstance(st.rudder, UdpSocketRudder):
                    # UDP
                    st.read_buf, st.addr = st.rudder.skt.recvfrom(65536)
                else:
                    # TCP
                    st.read_buf = bytearray(st.rudder.read(st.buf_size))
            except EOFError as e:
                BayLog.debug("%s EOF", self)
                st.read_buf = bytearray(b"")
            except BlockingIOError as e:
                BayLog.debug("%s No data (continue)", self)
                return
            except ssl.SSLWantReadError:
                BayLog.debug("%s Read more", self)
                return


            BayLog.debug("%s read %d bytes", self, len(st.read_buf))
            self.agent.send_read_letter(st, len(st.read_buf), st.addr, False)

        except Exception as e:
            BayLog.debug_e(e, traceback.format_stack(),"%s Unhandled error", self)
            self.agent.send_error_letter(st, e, traceback.format_stack(), False)

    def _on_writable(self, st: RudderState) -> None:

        try:
            if st.handshaking:
                try:
                    self._handshake_nonblock(st.rudder)
                    BayLog.debug("%s Handshake: done", self)
                    st.handshaking = False
                except ssl.SSLWantReadError:
                    BayLog.debug("%s Handshake: Need to read more st=%s", self, st)
                except ssl.SSLWantWriteError:
                    BayLog.debug("%s Handshake: Need to write more st=%s", self, st)

            if len(st.write_queue) == 0:
                raise IOError(f"{self.agent} No data to write: {st.rudder}")

            for i in range(0, len(st.write_queue)):
                wunit = st.write_queue[i]

                BayLog.debug("%s Try to write q[%d]: pkt=%s buflen=%d rd=%s closed=%s adr=%s", self, i, wunit.tag,
                             len(wunit.buf), st.rudder, st.closed, wunit.adr)

                if not st.closed:
                    if len(wunit.buf) == 0:
                        length = 0
                    else:
                        try:
                            if isinstance(st.rudder, UdpSocketRudder):
                                # UDP
                                length = st.rudder.skt.sendto(wunit.buf, wunit.adr)
                            else:
                                length = st.rudder.write(wunit.buf)
                        except (BlockingIOError, ssl.SSLWantWriteError) as e:
                            BayLog.debug("%s Write will be pended", self)
                            break
                            # self.agent.send_error_letter(st, e, False)

                    BayLog.debug("%s wrote %d bytes", self, length)
                    wunit.buf = wunit.buf[length::]
                    self.agent.send_wrote_letter(st, length, False)

                    if length < len(wunit.buf):
                        BayLog.debug("%s Data remains", self)
                        break

        except Exception as e:
            BayLog.debug_e(e, traceback.format_stack(),"%s Unhandled error", self)
            self.agent.send_error_letter(st, e, traceback.format_stack(), False)

    def _on_waked_up(self) -> None:
        BayLog.trace("%s On Waked Up", self)
        try:
            while True:
                IOUtil.recv_int32(self.select_wakeup_pipe[0])
        except BlockingIOError as e:
            pass

    def _handshake_nonblock(self, rd: Rudder) -> None:
        rd.key().do_handshake()


    @classmethod
    def op_mode(cls, mode):
        mode_str = "";
        if (mode & selectors.EVENT_READ) != 0:
            mode_str = "OP_READ";
        if (mode & selectors.EVENT_WRITE) != 0:
            if mode_str != "":
                mode_str += "|"
            mode_str += "OP_WRITE";
        return mode_str
