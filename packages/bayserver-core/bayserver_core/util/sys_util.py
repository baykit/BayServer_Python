import multiprocessing
import os
import platform
import selectors
import tempfile

from bayserver_core import bayserver as bs
from bayserver_core.bay_log import BayLog

class SysUtil:

    @classmethod
    def run_on_windows(cls):
        return platform.system() == "Windows"

    @classmethod
    def run_on_mac(cls):
        return platform.system() == 'Darwin'
    #
    # We set environment variable "PYCHARM" to 1 for debugging
    #
    @classmethod
    def run_on_pycharm(cls):
        return os.environ.get("PYCHARM") == "1"

    @classmethod
    def support_select_file(cls):
        with open(bs.BayServer.bserv_plan) as f:
            try:
                sel = selectors.DefaultSelector()
                sel.register(f, selectors.EVENT_READ)
                n = sel.select(0)
                return True
            except OSError as e:
                BayLog.debug_e(e, "select() failed")
                return False
            finally:
                if sel is not None:
                    sel.close()

    @classmethod
    def support_nonblock_file_read(cls):
        with open(bs.BayServer.bserv_plan) as f:
            try:
                import fcntl
                fcntl.fcntl(f, fcntl.F_SETFL, os.O_NONBLOCK)
                return True
            except ModuleNotFoundError or OSError as e:
                if BayLog.debug_mode():
                    BayLog.warn("fctl() failed: %s ", e)
                return False


    @classmethod
    def support_nonblock_file_write(cls):
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(dir, "test_file"), "wb") as f:
                try:
                    import fcntl
                    fcntl.fcntl(f, fcntl.F_SETFL, os.O_NONBLOCK)
                    return True
                except ModuleNotFoundError or OSError as e:
                    if BayLog.debug_mode():
                        BayLog.warn("fctl() failed: %s ", e)
                    return False

    @classmethod
    def support_select_pipe(cls):
        r, w = os.pipe()
        try:
            sel = selectors.DefaultSelector()
            sel.register(r, selectors.EVENT_READ)
            n = sel.select(0)
            sel.close()
            return True
        except OSError as e:
            if BayLog.debug_mode():
                BayLog.warn("select() failed: %s ", e)
                return False
        finally:
            os.close(r)
            os.close(w)

    @classmethod
    def support_nonblock_pipe_read(cls):
        r, w = os.pipe()
        try:
            import fcntl
            fcntl.fcntl(r, fcntl.F_SETFL, os.O_NONBLOCK)
            return True
        except ModuleNotFoundError or OSError as e:
            if BayLog.debug_mode():
                BayLog.warn("fctl() failed: %s ", e)
            return False
        finally:
            os.close(r)
            os.close(w)

    @classmethod
    def pid(cls):
        return os.getpid()


    @classmethod
    def processor_count(cls):
        return multiprocessing.cpu_count()


    @classmethod
    def support_unix_domain_socket_address(cls):
        return not SysUtil.run_on_windows()