from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_ROUTES = {
    "/": ("dashboard.html", "text/html; charset=utf-8"),
    "/dashboard.html": ("dashboard.html", "text/html; charset=utf-8"),
    "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
    "/dashboard.js": ("dashboard.js", "application/javascript; charset=utf-8"),
}
API_ROUTES = {"/observation", "/status", "/task", "/allow_act", "/base", "/reconnect", "/reload_model"}


class LiveHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], backend_url: str):
        super().__init__(server_address, LiveRequestHandler)
        parsed = urlparse(backend_url)
        if not parsed.scheme or not parsed.hostname:
            raise ValueError(f"Invalid backend URL: {backend_url}")
        self.backend_scheme = parsed.scheme
        self.backend_host = parsed.hostname
        self.backend_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.backend_base_path = parsed.path.rstrip("/")


class LiveRequestHandler(BaseHTTPRequestHandler):
    server_version = "RobotDashboardLive/1.0"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in STATIC_ROUTES:
            self._serve_static(path)
            return
        if path in API_ROUTES:
            self._proxy_request("GET")
            return
        self._send_json({"detail": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in API_ROUTES:
            self._proxy_request("POST")
            return
        self._send_json({"detail": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        del format, args

    def _serve_static(self, path: str) -> None:
        filename, content_type = STATIC_ROUTES[path]
        body = (BASE_DIR / filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy_request(self, method: str) -> None:
        live_server: LiveHTTPServer = self.server  # type: ignore[assignment]
        body = b""
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > 0:
            body = self.rfile.read(content_length)

        backend_path = f"{live_server.backend_base_path}{urlparse(self.path).path}"
        conn = HTTPConnection(live_server.backend_host, live_server.backend_port, timeout=15)
        headers = {}
        if body:
            headers["Content-Type"] = self.headers.get("Content-Type", "application/json")

        try:
            conn.request(method, backend_path, body=body if body else None, headers=headers)
            response = conn.getresponse()
            payload = response.read()
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except OSError as exc:
            self._send_json(
                {
                    "detail": "Failed to reach backend API",
                    "error": str(exc),
                    "backend": f"http://{live_server.backend_host}:{live_server.backend_port}{backend_path}",
                },
                status=HTTPStatus.BAD_GATEWAY,
            )
        finally:
            conn.close()

    def _send_json(self, payload: dict, *, status: HTTPStatus) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve web dashboard UI against a live backend API.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for the dashboard server.")
    parser.add_argument("--port", type=int, default=8080, help="Port for the dashboard server.")
    parser.add_argument(
        "--backend-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the live robot backend API.",
    )
    args = parser.parse_args()

    server = LiveHTTPServer((args.host, args.port), args.backend_url)
    print(f"Web dashboard running at http://{args.host}:{args.port}/")
    print(f"Proxying API requests to {args.backend_url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
