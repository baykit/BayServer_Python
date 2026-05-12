"""Process-shared libphp.so embedding runtime for PharosDocker.

Java port (1:1 with `PharosRuntime.java`) targeting Python's
multi_core=yes lifecycle:

  parent process              fork()              N child agents
  ---------------------------------------------------------------
  dlopen libphp.so
  patch php_embed_module
      .name      -> "fpm-fcgi"   (so opcache whitelists us)
      .ub_write  -> Python upcall (stream echo into tour.res)
  php_embed_init                  ->  inherited mmap'd opcache,
  php_request_shutdown                inherited libphp state
      (close auto request)               in every child
                                  ->  per request:
                                        php_request_startup
                                        zend_eval_string(include)
                                        php_request_shutdown

The parent never executes a PHP request itself; it just primes the
shared opcache + module state before forking. Children call `init`
again as a no-op (state already loaded).

ZTS handling: if the loaded libphp exposes `ts_resource_ex`, this is
a ZTS build and we register the current thread's TSRM pool lazily on
the first runScript call (matching Java). NTS builds skip that step.
"""

import ctypes
import os
import threading
import traceback

from bayserver_core.bay_log import BayLog
from bayserver_core.util.http_status import HttpStatus


# Offsets within `sapi_module_struct` on 64-bit Linux. These are stable
# across the PHP 8.x line; if you switch major version, re-derive with
# pahole on `php_embed_module`.
_NAME_OFFSET = 0       # char *name (first field)
_UB_WRITE_OFFSET = 48  # size_t (*ub_write)(const char *, size_t)

_PRETEND_SAPI_NAME = b"fpm-fcgi\x00"


class _ReqCtx:
    """Per-thread mutable context. Java's ThreadLocal<ReqCtx> equivalent."""

    __slots__ = ("tour", "headers_sent", "error", "tsrm_registered")

    def __init__(self):
        self.tour = None
        self.headers_sent = False
        self.error = None
        self.tsrm_registered = False


class PharosRuntime:

    # Module-level so the patched name + the ctypes upcall stub keep
    # their referents alive for the process lifetime. Losing the upcall
    # stub would dangle the .ub_write function pointer.
    _process_pinned = []
    _ctx_storage = threading.local()

    def __init__(self, lib_php_path):
        self.lib_php_path = lib_php_path
        self._lib = None
        self._php_request_startup = None
        self._php_request_shutdown = None
        self._zend_eval_string = None
        self._ts_resource_ex = None

    @classmethod
    def _ctx(cls):
        ctx = getattr(cls._ctx_storage, "ctx", None)
        if ctx is None:
            ctx = _ReqCtx()
            cls._ctx_storage.ctx = ctx
        return ctx

    def init(self):
        """One-time process bootstrap. Must run in the parent process
        before fork so children inherit the mmap'd opcache region."""
        BayLog.info("PharosRuntime: loading %s", self.lib_php_path)

        # RTLD_GLOBAL so libphp's extensions (opcache etc.) can resolve
        # libphp symbols against the same flat namespace ZEND_API uses.
        # Without it, opcache's MINIT can't find zend_alloc_globals.
        self._lib = ctypes.CDLL(self.lib_php_path,
                                mode=ctypes.RTLD_GLOBAL)

        # 1. Patch php_embed_module.{name, ub_write}.
        #    - name : "embed" -> "fpm-fcgi" so opcache's accel_find_sapi
        #             accepts us (= "embed" is not on its whitelist).
        #    - ub_write: default fwrite(stdout) -> Python upcall that
        #                streams bytes to tour.res.send_res_content.
        embed_addr = ctypes.cast(self._lib.php_embed_module,
                                  ctypes.c_void_p).value
        if embed_addr is None:
            raise RuntimeError(
                f"php_embed_module symbol not found in {self.lib_php_path}")

        # Spoofed SAPI name. The buffer must outlive the process; pin to
        # the class so the GC doesn't free it.
        name_buf = ctypes.create_string_buffer(_PRETEND_SAPI_NAME)
        PharosRuntime._process_pinned.append(name_buf)
        ctypes.memmove(
            embed_addr + _NAME_OFFSET,
            ctypes.byref(ctypes.c_void_p(ctypes.addressof(name_buf))),
            ctypes.sizeof(ctypes.c_void_p))

        # ub_write upcall: define as a CFUNCTYPE so the C side can call
        # back into Python. Same caveat as the name buffer -- keep a
        # reference on the class.
        ub_write_proto = ctypes.CFUNCTYPE(
            ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t)
        ub_write_stub = ub_write_proto(_ub_write_callback)
        PharosRuntime._process_pinned.append(ub_write_stub)

        # The stub is a Python object; its underlying function pointer
        # is accessible through ctypes.cast to c_void_p.
        ub_write_addr = ctypes.cast(ub_write_stub, ctypes.c_void_p).value
        ctypes.memmove(
            embed_addr + _UB_WRITE_OFFSET,
            ctypes.byref(ctypes.c_void_p(ub_write_addr)),
            ctypes.sizeof(ctypes.c_void_p))

        # 2. Resolve C calls. Set explicit argtypes/restype so ctypes
        #    doesn't truncate pointers on x86_64.
        self._lib.php_embed_init.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
        self._lib.php_embed_init.restype = ctypes.c_int

        self._lib.php_request_startup.argtypes = []
        self._lib.php_request_startup.restype = ctypes.c_int
        self._php_request_startup = self._lib.php_request_startup

        self._lib.php_request_shutdown.argtypes = [ctypes.c_void_p]
        self._lib.php_request_shutdown.restype = None
        self._php_request_shutdown = self._lib.php_request_shutdown

        self._lib.zend_eval_string.argtypes = [
            ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p]
        self._lib.zend_eval_string.restype = ctypes.c_int
        self._zend_eval_string = self._lib.zend_eval_string

        # ts_resource_ex only exists on ZTS builds. Probe via getattr so
        # NTS builds fall through cleanly.
        try:
            self._ts_resource_ex = self._lib.ts_resource_ex
            self._ts_resource_ex.argtypes = [
                ctypes.c_int, ctypes.c_void_p]
            self._ts_resource_ex.restype = ctypes.c_void_p
            BayLog.info("PharosRuntime: ZTS libphp detected "
                        "(ts_resource_ex present)")
        except AttributeError:
            self._ts_resource_ex = None
            BayLog.info("PharosRuntime: NTS libphp detected "
                        "(ts_resource_ex absent)")

        # 3. Bring PHP up; close the auto-started request so per-request
        #    boundaries start fresh per child.
        rc = self._lib.php_embed_init(0, None)
        if rc != 0:
            raise RuntimeError(f"php_embed_init returned {rc}")
        self._php_request_shutdown(None)

        BayLog.info("PharosRuntime: ready (libphp loaded, SAPI started)")

    def run_script(self, tour, php_code, label):
        """Run a PHP snippet on the current thread. Output streams to
        tour.res via the ub_write upcall as PHP echoes; this method
        does not return a body buffer.

        Returns True if any output was produced (= headers were sent),
        False if PHP wrote nothing (caller should send a 0-byte 200)."""
        ctx = PharosRuntime._ctx()
        try:
            # Lazy per-thread TSRM registration on ZTS builds. NTS skips.
            if self._ts_resource_ex is not None and not ctx.tsrm_registered:
                self._ts_resource_ex(0, None)
                ctx.tsrm_registered = True

            ctx.tour = tour
            ctx.headers_sent = False
            ctx.error = None

            # Per-request engine state (= the php-fpm-equivalent boundary).
            self._php_request_startup()
            try:
                code_b = php_code.encode("utf-8")
                label_b = label.encode("utf-8")
                rc = self._zend_eval_string(code_b, None, label_b)
                if rc != 0:
                    BayLog.warn("zend_eval_string returned %d for %s",
                                rc, label)
            finally:
                self._php_request_shutdown(None)

            # Surface any IOError stashed by the ub_write upcall.
            if ctx.error is not None:
                raise ctx.error

            return ctx.headers_sent
        except IOError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Pharos run_script failed: {label}") from e
        finally:
            ctx.tour = None
            ctx.error = None


def _ub_write_callback(buf, length):
    """ub_write upcall. Called from inside libphp during
    zend_eval_string when PHP code executes `echo` or `print`. Streams
    the bytes directly to the active tour's response without staging."""
    ctx = PharosRuntime._ctx()
    tour = ctx.tour
    if tour is None:
        # Fired outside a request (e.g. on module shutdown). Discard.
        return length

    try:
        # Lazy header send on the first chunk. We don't know the total
        # content length up front, so omit Content-Length; BayServer
        # will use chunked / connection-close framing as appropriate.
        if not ctx.headers_sent:
            tour.res.headers.set_status(HttpStatus.OK)
            tour.res.headers.set_content_type("text/html; charset=UTF-8")

            def _consume_cb(*_args, **_kwargs):
                pass

            tour.res.set_res_consume_listener(_consume_cb)
            tour.res.send_res_headers(tour.tour_id)
            ctx.headers_sent = True

        # buf is a c_char_p; ctypes string_at copies `length` bytes out.
        chunk = ctypes.string_at(buf, length)
        tour.res.send_res_content(tour.tour_id, chunk, 0, len(chunk))
        return length
    except IOError as e:
        if ctx.error is None:
            ctx.error = e
        return ctypes.c_size_t(-1).value
    except Exception:
        BayLog.error("ub_write upcall failed:\n%s",
                     "".join(traceback.format_exc()))
        return ctypes.c_size_t(-1).value
