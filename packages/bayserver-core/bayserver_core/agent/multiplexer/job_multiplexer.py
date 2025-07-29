import errno
import os, threading
import traceback
from typing import Tuple

from bayserver_core.agent import grand_agent as gs
from bayserver_core.agent.multiplexer.job_multiplexer_base import JobMultiplexerBase
from bayserver_core.agent.multiplexer.write_unit import WriteUnit
from bayserver_core.bay_log import BayLog
from bayserver_core.common.rudder_state import RudderState
from bayserver_core.rudder.rudder import Rudder
from bayserver_core.rudder.socket_rudder import SocketRudder
from bayserver_core.util.internet_address import InternetAddress
from bayserver_core.util.sys_util import SysUtil


class JobMultiplexer(JobMultiplexerBase):

    anchorable: bool
    pipe: Tuple[int, int]

    def __init__(self, agt: "gs.GrandAgent", anchorable: bool):
        super().__init__(agt, anchorable)


    def __str__(self):
        return f"JobMpx[{self.agent}]"

    ######################################################
    # Implements Multiplexer
    ######################################################

    def req_accept(self, rd: Rudder) -> None:
        BayLog.debug("%s reqAccept isShutdown=%s", self.agent, self.agent.aborted)
        if self.agent.aborted:
            return

        st = self.get_rudder_state(rd)

        def run():
            try:
                if self.agent.aborted:
                    return

                try:
                    client_skt = rd.key().accept()
                except BaseException as e:
                    self.agent.send_error_letter(st, e, traceback.format_stack(), True)
                    return

                BayLog.debug("%s Accepted skt=%s", self.agent, client_skt)
                if self.agent.aborted:
                    BayLog.error("%s Agent is not alive (close)", self.agent)
                    client_skt.close()
                else:
                    self.agent.send_accepted_letter(st, SocketRudder(client_skt), True)
            except Exception as e:
                BayLog.fatal_e(e)
                self.agent.shutdown()

            agent_thread = threading.Thread(target=run)
            agent_thread.start()

    def req_connect(self, rd: Rudder, adr: InternetAddress) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqConnect adr=%s rd=%s chState=%s", self.agent, adr, rd, st)

        def run():
            try:
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
                self.agent.send_connected_letter(st, False)
            except BaseException as e:
                self.agent.send_error_letter(st, e, traceback.format_stack(), False)

            agent_thread = threading.Thread(target=run)
            agent_thread.start()

    def req_read(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        if st is None:
            return

        BayLog.debug("%s reqRead rd=%s state=%s", self.agent, st.rudder, st)
        need_read = False
        with st.reading_lock:
            if not st.reading:
                need_read = True
                st.reading = True


        if need_read:
            self.next_read(st)

        st.access()


    def req_write(self, rd: Rudder, buf: bytearray, adr: InternetAddress, tag: object, lis) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqWrite st=%s", self.agent, st)

        if st is None or st.closed:
            BayLog.warn("%s Channel is closed(callback immediately): %s", self.agent, rd)
            lis.call()
            return

        unt = WriteUnit(buf, adr, tag, lis)
        with st.write_queue_lock:
            st.write_queue.append(unt)

        need_write = False
        with st.writing_lock:
            if not st.writing:
                need_write = True
                st.writing = True

        if need_write:
            self.next_write(st)

        st.access()


    def req_close(self, rd: Rudder) -> None:
        st = self.get_rudder_state(rd)
        BayLog.debug("%s reqClose st=%s", self.agent, st)
        if st is None:
            BayLog.warn("%s channel state not found: %s", self.agent, rd)
            return

        def run():
            try:
                self.close_rudder(rd)
                self.agent.send_closed_letter(st, True)
            except Exception as e:
                BayLog.fatal_e(e)
                self.agent.shutdown()

        agent_thread = threading.Thread(target=run)
        agent_thread.start()

        st.access()

    def cancel_read(self, rd: Rudder) -> None:
        pass

    def cancel_write(self, st: RudderState) -> None:
        pass

    def next_accept(self, st: RudderState) -> None:
        self.req_accept(st.rudder)

    def cancel_wait(self, rd: Rudder) -> None:
        pass

    def next_read(self, st: RudderState) -> None:

        def run():
            if st.closed:
                # channel is already closed
                BayLog.debug("%s Rudder is already closed: rd=%s", self.agent, st.rudder)
                return

            try:
                if st.handshaking:
                    st.rudder.key().handshake()
                    BayLog.debug("%s Handshake done (rd=%s)", self, st.rudder)
                    st.handshaking = False

                BayLog.debug("%s Try to Read (rd=%s)", self.agent, st.rudder)
                st.read_buf = st.rudder.read(st.buf_size)

                self.agent.send_read_letter(st, len(st.read_buf), None, True)


            except BaseException as e:
                self.agent.send_error_letter(st, e, traceback.format_stack(), True)

        agent_thread = threading.Thread(target=run)
        agent_thread.start()

    def next_write(self, st: RudderState) -> None:

        def run():
            BayLog.debug("%s next write st=%s", self.agent, st)

            if st is None or st.closed:
                BayLog.warn("%s Channel is closed: %s", self.agent, st)
                return

            u = st.write_queue[0]
            BayLog.debug("%s Try to write: pkt=%s buflen=%d closed=%s", self, u.tag, len(u.buf), st.closed)

            n = 0
            try:
                if not st.closed and len(u.buf) > 0:
                    n = st.rudder.write(u.buf)
                    u.buf = u.buf[n:]
            except BaseException as e:
                self.agent.send_error_letter(st, e, traceback.format_stack(), True)
                return

            self.agent.send_wrote_letter(st, n, True)

        agent_thread = threading.Thread(target=run)
        agent_thread.start()


    def is_non_blocking(self) -> bool:
        return False

    def use_async_api(self) -> bool:
        return False

    def on_busy(self) -> None:
        pass
