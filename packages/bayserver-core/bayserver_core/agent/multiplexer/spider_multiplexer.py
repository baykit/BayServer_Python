import errno
import os
import selectors
import socket
import ssl
import traceback
from selectors import SelectorKey

# TCP_QUICKACK is Linux-specific (value 12). The constant exists as a
# socket module attribute on Linux Python builds; on macOS / Windows the
# attribute is absent so we fall back to the raw value -- the setsockopt
# will fail silently if the kernel doesn't understand it.
_TCP_QUICKACK = getattr(socket, "TCP_QUICKACK", 12)
from typing import List

from bayserver_core import bayserver as bs
from bayserver_core.agent import grand_agent as ga
from bayserver_core.agent.multiplexer.multiplexer_base import MultiplexerBase
from bayserver_core.common.write_unit import WriteUnit
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

    anchorable: bool
    selector: selectors.BaseSelector
    rudders_to_register: List[Rudder]
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

        self.rudders_to_register = []

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
        self.selector.register(rd.key(), selectors.EVENT_READ, data=rd)
        st.accepting = True

    def req_connect(self, rd: Rudder, adr: InternetAddress) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqConnect adr=%s rd=%s chState=%s", self.agent, adr, rd, st)

        rd.set_non_blocking()

        err = rd.key().connect_ex(adr)
        if SysUtil.run_on_windows():
            ok = err == 10035
        else:
            ok = err == errno.EAGAIN or err == errno.EINPROGRESS
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

    def req_transfer(self, rd: Rudder, file_rd: Rudder, ofs: int, length: int, lis) -> None:
        """Direct Boarding (sendfile) request. Enqueues a file-mode WriteUnit;
        the sendfile syscall is issued in `_on_writable` when the socket becomes
        writable. Only supported on platforms where `os.sendfile` exists."""
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqTransfer st=%s ofs=%d len=%d file=%s", self, st, ofs, length, file_rd)

        if st is None or st.closed:
            BayLog.warn("%s Rudder is closed: %s", self, rd)
            if lis is not None:
                lis()
            return

        if not hasattr(os, "sendfile"):
            raise Sink("os.sendfile is not available on this platform")

        unt = WriteUnit.for_file(file_rd, ofs, length, lis)
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
                # modify() replaces data; preserve attached rudder.
                self.selector.modify(st.rudder.key(), op, data=st.rudder)

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
        first_register = len(self.rudders_to_register) == 0

        if rd.in_dirty_list:
            rd.pending_ops |= op
        else:
            rd.pending_ops = op
            rd.pending_to_connect = to_connect
            self.rudders_to_register.append(rd)
            rd.in_dirty_list = True

        if to_connect:
            rd.pending_to_connect = True

        if first_register:
            self.wakeup()


    def _register_channel_ops(self) -> int:
        if len(self.rudders_to_register) == 0:
            return 0

        nch = len(self.rudders_to_register)
        for rd in self.rudders_to_register:
            st = self.get_rudder_state(rd)
            if st is None:
                BayLog.debug("%s Try to register closed socket (Ignore)", self)
                rd.in_dirty_list = False
                rd.pending_ops = 0
                rd.pending_to_connect = False
                continue

            fileobj = rd.key()
            try:
                BayLog.debug("%s register op=%s rd=%s chState=%s", self, SpiderMultiplexer.op_mode(rd.pending_ops), rd, st)
                try:
                    key = self.selector.get_key(fileobj)
                    op = key.events
                    new_op = op | rd.pending_ops
                    if new_op != op:
                        BayLog.trace("%s Already registered op=%s update to %s", self, SpiderMultiplexer.op_mode(op), SpiderMultiplexer.op_mode(new_op))
                        self.selector.modify(fileobj, new_op, data=rd)
                except KeyError:
                    # channel is not registered in selector
                    BayLog.trace("%s Not registered", self)
                    self.selector.register(fileobj, rd.pending_ops, data=rd)

                if rd.pending_to_connect:
                    st.connecting = True

            except BaseException as e:
                BayLog.error_e(e, traceback.format_stack(), "%s Cannot register operation: %s", self, rd)

            rd.in_dirty_list = False
            rd.pending_ops = 0
            rd.pending_to_connect = False

        self.rudders_to_register.clear()
        return nch


    def _handle_channel(self, key: SelectorKey, events: int) -> None:

        ch = key.fileobj
        rd: Rudder = key.data
        if rd is None:
            BayLog.error("Rudder is not attached to key: ch=%s", ch)
            try:
                self.selector.unregister(ch)
            except (KeyError, ValueError) as e:
                BayLog.debug("%s Unregister error (Ignore): %s", self, e)
            return

        st = self.get_rudder_state(rd)
        if st is None:
            BayLog.error("Channel state is not registered: ch=%s", ch)
            try:
                self.selector.unregister(ch)
            except (KeyError, ValueError) as e:
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
                sk = self.selector.get_key(ch)
                op = sk.events & ~selectors.EVENT_WRITE
                if op != selectors.EVENT_READ:
                    BayLog.debug("%s Unregister channel (Write Off) chState=%s", self.agent, st)
                    self.selector.unregister(ch)
                else:
                    # modify() replaces data; preserve attached rudder.
                    self.selector.modify(ch, op, data=rd)

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
        # TCP_NODELAY on accepted client sockets: serving small responses
        # suffers ~40 ms Nagle/delayed-ACK stalls otherwise (small H2
        # control frames interleaved with body bytes, short HTTP/1
        # responses on keep-alive).
        try:
            if client_skt.family in (socket.AF_INET, socket.AF_INET6):
                client_skt.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as e:
            BayLog.debug("%s could not set TCP_NODELAY on accepted: %s",
                         self.agent, e)
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
            if st.handshaking and not isinstance(st.rudder, UdpSocketRudder):
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

            # Warp upstreams (php-fpm, AJP backends) leave Nagle on; the
            # kernel's delayed-ACK timer pairs with that to add a ~40 ms
            # stall per response in the few-MTU body range. Re-arm
            # TCP_QUICKACK on those sockets after each read so the next
            # ACK fires immediately. TCP_QUICKACK is one-shot on Linux
            # (= reverts after the next packet), hence the per-read call.
            # Skip for inbound (client-facing) sockets — clients set
            # TCP_NODELAY themselves and the per-read setsockopt would
            # cost CPU at high rps.
            if st.quick_ack:
                try:
                    st.rudder.key().setsockopt(
                        socket.IPPROTO_TCP, _TCP_QUICKACK, 1)
                except (OSError, AttributeError):
                    pass

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
                BayLog.debug("%s No data to write: %s", self, st.rudder)
                self.cancel_write(st)
                return

            if st.closed:
                return

            if isinstance(st.rudder, UdpSocketRudder):
                # UDP: each WriteUnit has its own destination, cannot combine.
                for i in range(0, len(st.write_queue)):
                    wunit = st.write_queue[i]

                    BayLog.debug("%s Try to write q[%d/%d]: pkt=%s buflen=%d rd=%s adr=%s",
                                 self, i, len(st.write_queue), wunit.tag, len(wunit.buf), st.rudder, wunit.adr)

                    if len(wunit.buf) == 0:
                        length = 0
                    else:
                        try:
                            length = st.rudder.skt.sendto(wunit.buf, wunit.adr)
                        except (BlockingIOError, ssl.SSLWantWriteError):
                            BayLog.debug("%s Write will be pended", self)
                            break

                    wunit.buf = wunit.buf[length:]
                    self.agent.send_wrote_letter(st, length, False)

                    if length < len(wunit.buf):
                        BayLog.debug("%s Data remains", self)
                        break
            else:
                head = st.write_queue[0]
                if head.skip_formalities():
                    # Direct Boarding: drive head unit forward via os.sendfile.
                    # File units are not gathered with buffer units.
                    self._on_writable_sendfile(st, head)
                    return

                # TCP / TLS: gather buffer units (up to first file unit) into
                # one write to reduce syscall count (Java 862441d writev
                # equivalent).
                combined_parts = []
                for w in st.write_queue:
                    if w.skip_formalities():
                        break
                    if len(w.buf) > 0:
                        combined_parts.append(bytes(w.buf))
                if not combined_parts:
                    return
                combined = combined_parts[0] if len(combined_parts) == 1 else b"".join(combined_parts)

                BayLog.debug("%s Try to write gathered: bufs=%d total=%d rd=%s",
                             self, len(st.write_queue), len(combined), st.rudder)

                try:
                    n = st.rudder.write(combined)
                except (BlockingIOError, ssl.SSLWantWriteError):
                    BayLog.debug("%s Write will be pended", self)
                    return

                BayLog.debug("%s wrote %d bytes (gathered)", self, n)
                self.agent.send_wrote_letter(st, n, False)

                # Distribute n across the queued buffer WriteUnits, oldest
                # first. Stop at first file unit (handled separately).
                remaining = n
                for wunit in st.write_queue:
                    if wunit.skip_formalities():
                        break
                    blen = len(wunit.buf)
                    if blen == 0:
                        continue
                    if remaining >= blen:
                        remaining -= blen
                        wunit.buf = bytearray()
                    else:
                        wunit.buf = wunit.buf[remaining:]
                        remaining = 0
                        break

        except Exception as e:
            BayLog.debug_e(e, traceback.format_stack(),"%s Unhandled error", self)
            self.agent.send_error_letter(st, e, traceback.format_stack(), False)

    def _on_writable_sendfile(self, st: RudderState, unit: WriteUnit) -> None:
        """Drive a file-mode WriteUnit forward via os.sendfile. Loops until the
        socket would block or the unit is fully consumed."""
        try:
            out_fd = st.rudder.fileno()
            in_fd = unit.file.fileno()
        except OSError as e:
            BayLog.error_e(e, traceback.format_stack(), "%s sendfile fd lookup failed", self)
            self.agent.send_error_letter(st, e, traceback.format_stack(), False)
            return

        while unit.has_remaining():
            try:
                n = os.sendfile(out_fd, in_fd, unit.position(), unit.remaining())
            except BlockingIOError:
                BayLog.debug("%s sendfile would block", self)
                return
            except OSError as e:
                BayLog.debug_e(e, traceback.format_stack(), "%s sendfile error", self)
                self.agent.send_error_letter(st, e, traceback.format_stack(), False)
                return

            if n == 0:
                # EOF on input file before declared length completed. Mark the
                # remaining bytes as consumed so the unit does not stall.
                BayLog.debug("%s sendfile reached EOF early (remaining=%d)", self, unit.remaining())
                self.agent.send_wrote_letter(st, unit.remaining(), False)
                unit.forward(unit.remaining())
                return

            BayLog.debug("%s sendfile sent %d bytes (remaining=%d)", self, n, unit.remaining() - n)
            unit.forward(n)
            self.agent.send_wrote_letter(st, n, False)

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
