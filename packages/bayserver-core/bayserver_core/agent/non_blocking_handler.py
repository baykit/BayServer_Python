import io
import os
import socket
import threading
import time
import errno
import selectors

from bayserver_core import bayserver as bs
from bayserver_core.agent.timer_handler import TimerHandler
from bayserver_core.bay_log import BayLog
from bayserver_core.sink import Sink
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.util.exception_util import ExceptionUtil


class NonBlockingHandler(TimerHandler):

    OP_READ = 1
    OP_WRITE = 2


    class ChannelState:

        def __init__(self, ch, lis):
            self.channel = ch
            self.listener = lis
            self.accepted = False
            self.connecting = False
            self.closing = False
            self.last_access_time = None

        def access(self):
            self.last_access_time = time.time()

        def __str__(self):
            if self.listener:
                s = str(self.listener)
            else:
                s = str(super())
            if self.closing:
                s += " closing=true";
            return s

    class ChannelOperation:

        def __init__(self, ch, op, connect=False, close=False):
            self.ch = ch
            self.op = op
            self.connect = connect
            self.close = close


    def __init__(self, agent):
        self.agent = agent
        self.listener = None
        self.channel_map = {}
        self.channel_count = 0
        self.lock = threading.RLock()
        self.operations = []
        self.operations_lock = threading.RLock()

        agent.add_timer_handler(self)

    def __str__(self):
        return str(self.agent)

    ######################################################
    # Implements TimerHandler
    ######################################################

    def on_timer(self):
        self.close_timeout_sockets()

    ######################################################
    # Custom methods
    ######################################################

    def handle_channel(self, key, events):

        ch = key.fileobj
        #BayLog.trace("%s Handle channel: readable=%s writable=%s fd=%s",
        #             self.agent, events & selectors.EVENT_READ, events & selectors.EVENT_WRITE, ch)

        ch_state = self.find_channel_state(ch)
        if ch_state is None:
            BayLog.error("Channel state is not registered: fd=%s", ch)
            try:
                self.agent.selector.unregister(ch)
            except ValueError as e:
                BayLog.debug("%s Unregister error (Ignore): %s", self, e)
            return

        BayLog.debug("%s chState=%s Handle channel: readable=%s writable=%s connecting=%s closing=%s",
                     self.agent, ch_state, events & selectors.EVENT_READ, events & selectors.EVENT_WRITE,
                     ch_state.connecting, ch_state.closing)

        next_action = None
        try:

            if ch_state.closing:
                next_action = NextSocketAction.CLOSE

            elif ch_state.connecting:
                ch_state.connecting = False
                # connectable
                next_action = ch_state.listener.on_connectable(ch)
                if next_action is None:
                    raise Sink("unknown next action")
                elif next_action == NextSocketAction.READ:
                    # "Write-OP Off"
                    key = self.agent.selector.get_key(ch)
                    op = key.events & ~selectors.EVENT_WRITE
                    if op != selectors.EVENT_READ:
                        BayLog.debug("%s Unregister channel (Write Off) chState=%s", self.agent, ch_state)
                        self.agent.selector.unregister(ch)
                    else:
                        self.agent.selector.modify(ch, op)


            else:
                if events & selectors.EVENT_READ != 0:
                    next_action = ch_state.listener.on_readable(ch)
                    if next_action is None:
                        raise Sink("unknown next action")
                    elif next_action == NextSocketAction.WRITE:
                        key = self.agent.selector.get_key(ch)
                        op = key.events | selectors.EVENT_WRITE
                        self.agent.selector.modify(ch, op)

                if (next_action != NextSocketAction.CLOSE) and (events & selectors.EVENT_WRITE != 0):
                    # writable
                    next_action = ch_state.listener.on_writable(ch)
                    if next_action is None:
                        raise Sink("unknown next action")
                    elif next_action == NextSocketAction.READ:
                        # Handle as "Write Off"
                        key = self.agent.selector.get_key(ch)
                        op = key.events & ~selectors.EVENT_WRITE
                        if op != selectors.EVENT_READ:
                            BayLog.debug("%s Unregister channel (Write Off) chState=%s",self.agent, ch_state)
                            self.agent.selector.unregister(ch)
                        else:
                            self.agent.selector.modify(ch, op)


            if next_action is None:
                raise Sink("unknown next action")

        except Sink as e:
            raise e

        except BaseException as e:
            if isinstance(e, EOFError):
                BayLog.info("%s Socket closed by peer: skt=%s", self, ch.inspect)
            elif isinstance(e, OSError):
                BayLog.info("%s O/S error: %s (skt=%s)", self, ExceptionUtil.message(e), ch)
            else:
                BayLog.info("%s Unhandled error error: %s (skt=%s)", self, e, ch)
                raise e

            # Cannot handle Exception anymore
            ch_state.listener.on_error(ch, e)
            next_action = NextSocketAction.CLOSE

        cancel = False
        ch_state.access()
        BayLog.trace("%s next=%d chState=%s", self, next_action, ch_state)
        if next_action == NextSocketAction.CLOSE:
            self.close_channel(ch, ch_state)
            cancel = False  # already canceled in close_channel method
        elif next_action == NextSocketAction.SUSPEND:
            cancel = True

        elif (next_action == NextSocketAction.CONTINUE or
                next_action == NextSocketAction.READ or
                next_action == NextSocketAction.WRITE):
            pass

        else:
            RuntimeError(f"IllegalState:: {next_action}")

        if cancel:
            BayLog.trace("%s cancel key chState=%s", self, ch_state);
            try:
                self.agent.selector.unregister(ch)
            except ValueError as e:
                BayLog.warn_e(e)


    def register_channel_ops(self):
        if len(self.operations) == 0:
            return 0

        #BayLog.info("%s register op list: %s", self, self.operations)
        with self.operations_lock:
            nch = len(self.operations)
            for ch_op in self.operations:
                st = self.find_channel_state(ch_op.ch)
                try:
                    if ch_op.ch.fileno() == -1:
                        BayLog.debug("%s Try to register closed socket (Ignore)", self)
                        continue
                except BaseException as e:
                    BayLog.error_e(e, "%s get fileno error %s", self, ch_op.ch)
                    continue

                try:
                    BayLog.debug("%s register op=%s fd=%d chState=%s", self, NonBlockingHandler.op_mode(ch_op.op), ch_op.ch.fileno(), st)
                    try:
                        key = self.agent.selector.get_key(ch_op.ch)
                        op = key.events;
                        new_op = op | ch_op.op;
                        BayLog.trace("%s Already registered op=%s update to %s", self, NonBlockingHandler.op_mode(op), NonBlockingHandler.op_mode(new_op));
                        self.agent.selector.modify(ch_op.ch, new_op)
                    except KeyError:
                        # channel is not registered in selector
                        BayLog.trace("%s Not registered", self);
                        self.agent.selector.register(ch_op.ch, ch_op.op)

                    if ch_op.connect:
                        if st is None:
                            BayLog.warn("%s register connect but ChannelState is null", self);
                        else:
                            st.connecting = True

                    elif ch_op.close:
                        if st is None:
                            BayLog.warn("%s chState=%s register close but ChannelState", self);
                        else:
                            st.closing = True

                except BaseException as e:
                    cst = self.find_channel_state(ch_op.ch)
                    BayLog.error_e(e, "%s Cannot register operation: %s", self, cst.listener if cst is not None else None)

            self.operations.clear()
            return nch



    def close_timeout_sockets(self):
        if len(self.channel_map) == 0:
            return

        close_list = []
        now = time.time()
        for ch_state in self.channel_map.values():
            if ch_state.listener is not None:
                try:
                    duration = int(now - ch_state.last_access_time)
                    if ch_state.listener.check_timeout(ch_state.channel, duration):
                        BayLog.debug("%s timeout: fd=%s chState=%s", self, ch_state.channel.fileno(), ch_state)
                        close_list.append(ch_state)

                except IOError as e:
                    BayLog.error_e(e)
                    close_list.append(ch_state)

        for ch_state in close_list:
            self.close_channel(ch_state.channel, ch_state)


    def add_channel_listener(self, ch, lis):
        ch_state = NonBlockingHandler.ChannelState(ch, lis)
        self.add_channel_state(ch, ch_state)
        ch_state.access()
        return ch_state


    def ask_to_start(self, ch):
        BayLog.debug("%s askToStart: fd=%s", self.agent, ch);
        if not isinstance(ch, io.IOBase) and not isinstance(ch, socket.socket):
            raise Sink("Invalid channel")

        ch_state = self.find_channel_state(ch)
        ch_state.accepted = True

        #self.ask_to_read(ch)

    def ask_to_connect(self, ch, addr):
        if not isinstance(ch, io.IOBase) and not isinstance(ch, socket.socket):
            raise Sink("Invalid channel")

        ch_state = self.find_channel_state(ch)
        BayLog.debug("%s askToConnect addr=%s fd=%s chState=%s", self, addr, ch, ch_state)

        err = ch.connect_ex(addr)
        if bs.SysUtil.run_on_windows():
            ok = err == 10035
        else:
            ok = err == errno.EINPROGRESS
        ok |= (err == 0)

        if not ok:
            BayLog.error("%s connect error: adr=%s %s(%d)", self, addr, os.strerror(err), err)
            raise IOError("Connect failed: " + str(addr))

        ch_state.is_connecting = True

        self.add_operation(ch, selectors.EVENT_WRITE, connect=True)

    def ask_to_read(self, ch):
        if not isinstance(ch, io.IOBase) and not isinstance(ch, socket.socket):
            raise Sink("Invalid channel")
        if ch.fileno() < 0:
            raise IOError("Channel is closed")

        ch_state = self.find_channel_state(ch)
        BayLog.debug("%s askToRead chState=%s", self, ch_state);

        self.add_operation(ch, selectors.EVENT_READ)

        if ch_state is not None:
            ch_state.access()

    def ask_to_write(self, ch):
        if not isinstance(ch, io.IOBase) and not isinstance(ch, socket.socket):
            raise Sink("Invalid channel")
        if ch.fileno() < 0:
            BayLog.warn("%s Channel is closed: %s", self, ch)
            return

        ch_state = self.find_channel_state(ch)
        BayLog.debug("%s askToWrite chState=%s", self, ch_state);

        self.add_operation(ch, selectors.EVENT_WRITE)

        if ch_state is None:
            BayLog.error("Unknown channel (or closed)")
            return

        ch_state.access()



    def ask_to_close(self, ch):
        ch_state = self.find_channel_state(ch)
        BayLog.debug("%s askToClose fd=%s chState=%s", self, ch, ch_state)

        if ch_state is None:
            BayLog.warn("%s channel state not found: %s", self, ch)
            return

        ch_state.is_closing = True
        self.add_operation(ch, selectors.EVENT_WRITE, close=True)

        ch_state.access()

    def close_all(self):
        for ch in self.channel_map.keys():
            st = self.find_channel_state(ch)
            self.close_channel(ch, st)

    # private
    def add_operation(self, ch, op, close=False, connect=False):
        with self.operations_lock:
            found = False
            for ch_op in self.operations:
                if ch_op.ch == ch:
                    ch_op.op |= op
                    ch_op.close = ch_op.close or close
                    ch_op.connect = ch_op.connect or connect
                    found = True
                    BayLog.debug("%s Update operation: %s fd=%d", self, NonBlockingHandler.op_mode(ch_op.op), ch_op.ch.fileno())
            if not found:
                BayLog.debug("%s New operation: %s fd=%d", self, NonBlockingHandler.op_mode(op), ch.fileno());
                self.operations.append(NonBlockingHandler.ChannelOperation(ch, op, connect=connect, close=close))

        self.agent.wakeup()


    def close_channel(self, ch, ch_state):
        BayLog.debug("%s Close fd=%d chState=%s", self, ch.fileno(), ch_state)

        if ch_state is None:
            ch_state = self.find_channel_state(ch)

        if ch_state.accepted and self.agent.accept_handler:
           self.agent.accept_handler.on_closed()

        if ch_state.listener is not None:
            ch_state.listener.on_closed(ch)

        self.remove_channel_state(ch)
        try:
            self.agent.selector.unregister(ch)
        except KeyError or ValueError as e:
            BayLog.debug("%s Unregister error (Ignore): fd=%d chState=%s %s", self, ch.fileno(), ch_state, e)

        ch.close()


    def add_channel_state(self, ch, ch_state):
        BayLog.trace("%s add_channel_state fd=%s chState=%s", self, ch.fileno(), ch_state);

        with self.lock:
            self.channel_map[ch] = ch_state
        self.channel_count += 1


    def remove_channel_state(self, ch):
        #BayLog.trace("%s remove ch %s", self.agent, ch);

        with self.lock:
            if ch not in self.channel_map.keys():
                raise Sink("Channel is not in list (already removed?): %s", ch)
            del self.channel_map[ch]
        self.channel_count -= 1


    def find_channel_state(self, ch):
        with self.lock:
            return self.channel_map.get(ch)


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


