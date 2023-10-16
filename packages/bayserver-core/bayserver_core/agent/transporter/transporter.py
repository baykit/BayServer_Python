import ssl
import threading
from abc import ABCMeta, abstractmethod

from bayserver_core.agent.channel_listener import ChannelListener
from bayserver_core.agent.next_socket_action import NextSocketAction
from bayserver_core.agent.upgrade_exception import UpgradeException
from bayserver_core.bay_log import BayLog
from bayserver_core.protocol.protocol_exception import ProtocolException
from bayserver_core.sink import Sink
from bayserver_core.util.data_consume_listener import DataConsumeListener
from bayserver_core.util.reusable import Reusable
from bayserver_core.util.valve import Valve
from bayserver_core.util.postman import Postman


class Transporter(ChannelListener, Reusable, Valve, Postman, metaclass=ABCMeta):

    class WriteUnit:

        def __init__(self, buf, adr, tag, lis):
            self.buf = buf
            self.adr = adr
            self.tag = tag
            self.listener = lis

        def done(self):
            if self.listener is not None:
                if isinstance(self.listener, DataConsumeListener):
                    self.listener.done()
                else:
                    self.listener()


    @abstractmethod
    def secure(self):
        pass

    @abstractmethod
    def handshake_nonblock(self):
        pass

    @abstractmethod
    def handshake_finished(self):
        pass

    @abstractmethod
    def read_nonblock(self):
        pass

    @abstractmethod
    def write_nonblock(self, buf, adr):
        pass

    def __init__(self, server_mode, bufsize, trace_ssl, write_only=False):
        self.server_mode = server_mode
        self.trace_ssl = trace_ssl
        self.data_listener = None
        self.ch = None
        self.write_queue = []
        self.finale = None
        self.initialized = None
        self.ch_valid = None
        self.socket_io = None
        self.handshaked = None
        self.capacity = bufsize
        self.lock = threading.RLock()
        self.non_blocking_handler = None
        self.reset()
        self.write_only = write_only

    def __str__(self):
        return f"tpt[{self.data_listener}]"

    def init(self, ch_hnd, ch, lis):

        if self.initialized:
            BayLog.error("%s This transporter is already in use by channel: %s", self, self.ch)
            raise Sink("IllegalState")

        if len(self.write_queue) != 0:
            raise Sink()

        self.non_blocking_handler = ch_hnd
        self.data_listener = lis
        self.ch = ch
        self.initialized = True
        self.set_valid(True)
        self.handshaked = False
        self.non_blocking_handler.add_channel_listener(ch, self)

    ######################################################
    # Implements Reusable
    ######################################################
    def reset(self):

        # Check write queue
        if len(self.write_queue) > 0:
            raise Sink("Write queue is not empty")

        self.finale = False
        self.initialized = False
        self.ch = None
        self.set_valid(False)
        self.handshaked = False
        self.socket_io = None
        self.write_only = False

    ######################################################
    # Implements Postman
    ######################################################
    def post(self, buf, adr, tag, lisnr=None):
        self.check_initialized()

        BayLog.debug("%s post: %s len=%d", self, tag, len(buf))

        with self.lock:
            if not self.ch_valid:
                raise IOError(f"{self} Channel is invalid, Ignore")
            else:
                unt = Transporter.WriteUnit(buf, adr, tag, lisnr)
                self.write_queue.append(unt)

                BayLog.trace("%s post %s->askToWrite", self, tag)
                self.non_blocking_handler.ask_to_write(self.ch)


    ######################################################
    # Implements Valve
    ######################################################
    def open_valve(self):
        BayLog.debug("%s resume", self)
        self.non_blocking_handler.ask_to_read(self.ch)



    def abort(self):
        BayLog.debug("%s abort", self)
        self.non_blocking_handler.ask_to_close(self.ch)

    def is_zombie(self):
        return self.ch is not None and not self.ch_valid


    ######################################################
    # Implements ChannelListener
    ######################################################

    def on_readable(self, chk_ch):
        self.check_channel(chk_ch)
        BayLog.trace("%s on_readable", self)

        if not self.handshaked:
            try:
                self.handshake_nonblock()
                BayLog.debug("%s Handshake done", self.data_listener)
                self.handshake_finished()
                self.handshaked = True
            except ssl.SSLWantReadError:
                BayLog.debug("%s Need to read more", self.data_listener)
                return NextSocketAction.CONTINUE


        try:
            read_buf, adr = self.read_nonblock()
        except EOFError as e:
            BayLog.debug("%s EOF", self)
            self.set_valid(False)
            return self.data_listener.notify_eof()
        except BlockingIOError as e:
            BayLog.debug("%s No data (continue)", self)
            return NextSocketAction.CONTINUE
        except ssl.SSLWantReadError:
            BayLog.debug("%s Read more", self)
            return NextSocketAction.CONTINUE
        except ConnectionRefusedError as e:
            BayLog.error("%s Connection refused", self)
            self.set_valid(False)
            return NextSocketAction.CLOSE


        BayLog.trace("%s read %d bytes", self, len(read_buf))
        if len(read_buf) == 0:
            return self.data_listener.notify_eof()

        try:
            next_action = self.data_listener.notify_read(read_buf, adr)
            if next_action is None:
                raise Sink("Next action is empty")
            BayLog.trace("%s returned from notify_read(). next action=%d", self.data_listener, next_action)
            return next_action

        except UpgradeException as e:
            BayLog.debug("%s Protocol upgrade", self.data_listener)
            return self.data_listener.notify_read(read_buf, adr)

        except ProtocolException as e:
            close = self.data_listener.notify_protocol_error(e)

            if not close and self.server_mode:
                return NextSocketAction.CONTINUE
            else:
                return NextSocketAction.CLOSE

        except IOError as e:
            # IOError which occur in notify_XXX must be distinguished from
            # it which occur in handshake or readNonBlock.
            self.on_error(chk_ch, e)
            return NextSocketAction.CLOSE

    def on_writable(self, chk_ch):
        self.check_channel(chk_ch)

        BayLog.trace("%s Writable", self)

        if not self.ch_valid:
            return NextSocketAction.CLOSE

        if not self.handshaked:
            try:
                self.handshake_nonblock()
                BayLog.debug("%s Handshake: done", self.data_listener)
                self.handshake_finished()
                self.handshaked = True
            except ssl.SSLWantReadError:
                BayLog.debug("%s Handshake: Need to read more", self.data_listener)
                return NextSocketAction.CONTINUE
            except ssl.SSLWantWriteError:
                BayLog.debug("%s Handshake: Need to write more", self.data_listener)
                return NextSocketAction.CONTINUE

        empty = False
        while True:
            # BayLog.debug "#{self} Send queue len=#{@write_queue.length}"
            wunit = None

            with self.lock:
                if len(self.write_queue) == 0:
                    empty = True
                    break
                wunit = self.write_queue[0]

            if empty:
                break

            BayLog.debug("%s Try to write: pkt=%s buflen=%d ch=%d chValid=%s adr=%s", self, wunit.tag,
                         len(wunit.buf), self.ch.fileno(), self.ch_valid, wunit.adr)
            #BayLog.info("buf=%s", wunit.buf)

            if self.ch_valid and len(wunit.buf) > 0:
                try:
                    length = self.write_nonblock(wunit.buf, wunit.adr)
                    BayLog.trace("%s write %d bytes", self, length)
                    wunit.buf = wunit.buf[length::]
                    if len(wunit.buf) > 0:
                        # Data remains
                        break

                except (BlockingIOError, ssl.SSLWantWriteError):
                    BayLog.debug("%s Write will be pended", self)
                    # Wait next chance to write
                    break

            # packet send complete
            wunit.done()

            with self.lock:
                if len(self.write_queue) == 0:
                    raise Sink("%s Write queue is empty", self)
                self.write_queue.pop(0)
                empty = len(self.write_queue) == 0

            if empty:
                break

        if empty:
            if self.finale:
                BayLog.trace("%s finale return Close", self)
                state = NextSocketAction.CLOSE
            elif self.write_only:
                state = NextSocketAction.SUSPEND
            else:
                state = NextSocketAction.READ # will be handled as "Write Off"
        else:
            state = NextSocketAction.CONTINUE

        return state

    def on_connectable(self, chk_ch):
        self.check_channel(chk_ch)
        BayLog.debug("%s onConnectable (^o^)/: ch=%d", self, chk_ch.fileno())

        # check connection by sending 0 bytes data.
        try:
            self.ch.send(b"")
        except ssl.SSLWantReadError:
            # Not handshaked (OK)
            pass
        except IOError as e:
            BayLog.error_e(e, "Connect failed: %s", e)
            return NextSocketAction.CLOSE

        return self.data_listener.notify_connect()

    def check_timeout(self, chk_ch, duration):
        self.check_channel(chk_ch)

        return self.data_listener.check_timeout(duration)

    def on_error(self, chk_ch, e):
        self.check_channel(chk_ch)
        BayLog.trace("%s onError: %s", self, e)

        try:
            raise e
        except ssl.SSLError as e:
            if self.trace_ssl:
                BayLog.error_e(e, "%s SSL Error: %s", self, e)
            else:
                BayLog.debug_e(e, "%s SSL Error: %s", self, e)
        except BaseException as e:
            BayLog.error_e(e)

    def on_closed(self, chk_ch):
        try:
            self.check_channel(chk_ch)
        except BaseException as e:
            BayLog.error_e(e)
            return

        self.set_valid(False)

        with self.lock:
            # Clear queue
            for wunit in self.write_queue:
                wunit.done()
            self.write_queue.clear()

            self.data_listener.notify_close()

    def flush(self):
        self.check_initialized()

        BayLog.debug("%s flush", self)

        if self.ch_valid:
            empty = False
            with self.lock:
                empty = len(self.write_queue) == 0

            if not empty:
                BayLog.debug("%s flush->askToWrite", self)

                self.non_blocking_handler.ask_to_write(self.ch)

    def post_end(self):
        self.check_initialized()

        BayLog.debug("%s postEnd valid=%s", self, self.ch_valid)

        # setting order is QUITE important  finalState->finale
        self.finale = True

        if self.ch_valid:
            empty = False
            with self.lock:
                empty = len(self.write_queue) == 0

            if not empty:
                BayLog.debug("%s Tpt: sendEnd->askToWrite", self)
                self.non_blocking_handler.ask_to_write(self.ch)


    def check_channel(self, chk_ch):
        if chk_ch != self.ch:
            raise Sink(f"Invalid transporter instance (ships was returned?): {chk_ch}")

    def check_initialized(self):
        if not self.initialized:
            raise Sink("Illegal State")

    def set_valid(self, valid):
        self.ch_valid = valid

