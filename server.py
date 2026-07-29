"""HTTP diagnostics endpoint used by the on-call runbook to reach internal hosts.

GET /diagnostics?host=10.0.0.7  ->  raw ping output for that host.
"""

import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

LISTEN_ADDRESS = "127.0.0.1"
LISTEN_PORT = 8080
PING_COUNT = "2"
PING_TIMEOUT_SECONDS = 10


def probe_host(host: str) -> str:
    """Return the raw ping output for `host`.

    This is the planted SAST finding: `host` arrives straight from the HTTP
    query string and is concatenated into a shell command line, so a request
    for `?host=1.1.1.1;id` also runs `id` on the server (CWE-78, OS command
    injection). Fix instructions live in README.md / server_fixed.py.
    """
    command = "ping -c " + PING_COUNT + " " + host
    return subprocess.check_output(command, shell=True, text=True, timeout=PING_TIMEOUT_SECONDS)


class DiagnosticsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/diagnostics":
            self.send_error(404, "unknown path")
            return

        host = parse_qs(parsed.query).get("host", [""])[0]
        if not host:
            self.send_error(400, "missing host parameter")
            return

        try:
            output = probe_host(host)
        except subprocess.SubprocessError as err:
            self.send_error(502, "probe failed: {0}".format(err))
            return

        self._respond(output)

    def _respond(self, body_text: str) -> None:
        body = body_text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    HTTPServer((LISTEN_ADDRESS, LISTEN_PORT), DiagnosticsHandler).serve_forever()


if __name__ == "__main__":
    main()

