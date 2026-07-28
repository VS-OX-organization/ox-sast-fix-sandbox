"""Fixed counterpart of server.py — same behavior, no command injection.

Swap it in with `cp server_fixed.py server.py` (or apply fix.patch, which is
generated from this file). Re-arm the sandbox with `git checkout -- server.py`.

GET /diagnostics?host=10.0.0.7  ->  raw ping output for that host.
"""

import ipaddress
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

LISTEN_ADDRESS = "127.0.0.1"
LISTEN_PORT = 8080
PING_COUNT = "2"
PING_TIMEOUT_SECONDS = 10


def probe_host(host: str) -> str:
    """Return the raw ping output for `host`.

    `host` is caller-controlled, so it is validated as a bare IP address and
    passed as a separate argv entry with no shell involved. Neither step alone
    is enough: validation without argv still trusts the shell parser, argv
    without validation still lets a caller pass ping flags.
    """
    ipaddress.ip_address(host)
    return subprocess.check_output(
        ["ping", "-c", PING_COUNT, host],
        shell=False,
        text=True,
        timeout=PING_TIMEOUT_SECONDS,
    )


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
        except ValueError:
            self.send_error(400, "host must be an IP address")
            return
        except subprocess.SubprocessError:
            self.send_error(502, "probe failed")
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

