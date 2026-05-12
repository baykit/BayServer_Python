"""Per-tour content handler: when the request body is fully received,
runs the requested .php file via the embedded libphp runtime.

The runtime streams PHP's `echo` output directly to
`tour.res.send_res_content` from inside its ub_write upcall, so the
only thing this handler does after dispatching the script is close the
response (or, if PHP wrote nothing, send a zero-byte 200).
"""

import traceback

from bayserver_core.bay_log import BayLog
from bayserver_core.http_exception import HttpException
from bayserver_core.tour.req_content_handler import ReqContentHandler
from bayserver_core.tour.tour import Tour
from bayserver_core.util.http_status import HttpStatus


class PharosContentHandler(ReqContentHandler):

    def __init__(self, tour, file_path, runtime):
        self.tour = tour
        self.file_path = file_path
        self.runtime = runtime

    def on_read_req_content(self, tur, buf, start, length, lis):
        # Body upload not yet wired into PHP's $_POST.
        BayLog.debug("%s pharos:on_read_content len=%d (ignored for now)",
                     tur, length)
        tur.req.consumed(tur.tour_id, length, lis)

    def on_end_req_content(self, tur):
        BayLog.debug("%s pharos:end_content file=%s", tur, self.file_path)

        # PHP eval text: include the .php file. Single-quoted absolute
        # path; backslash- and quote-escape defensively.
        safe_path = self.file_path.replace("\\", "\\\\").replace("'", "\\'")
        script = f"include '{safe_path}';"

        try:
            wrote_anything = self.runtime.run_script(
                tur, script, f"pharos:{tur.req.uri}")
        except Exception as e:
            BayLog.error_e(e, traceback.format_stack(),
                           "pharos: run_script failed: %s", self.file_path)
            # If headers haven't gone out yet, surface the error.
            # Otherwise the response is partially sent and we just close
            # it best-effort below.
            raise HttpException(HttpStatus.INTERNAL_SERVER_ERROR,
                                f"Pharos execution failed: {e}")

        if not wrote_anything:
            # PHP produced no output; emit a zero-byte 200 so the tour
            # can complete normally.
            tur.res.headers.set_status(HttpStatus.OK)
            tur.res.headers.set_content_type("text/html; charset=UTF-8")
            tur.res.headers.set_content_length(0)

            def _consume_cb(*_args, **_kwargs):
                pass

            tur.res.set_res_consume_listener(_consume_cb)
            tur.res.send_res_headers(tur.tour_id)

        tur.res.end_res_content(tur.tour_id)

    def on_abort_req(self, tur):
        BayLog.debug("%s pharos:on_abort", tur)
        return True
