"""A local web GUI for PolyForge -- stdlib only (http.server), matching the
package's own zero-dependency ethos: no Flask/FastAPI to install just to get
a browser front end onto the same `templates`/`llm_backend`/`render`/
`preview_export` calls the CLI already uses.

Everything under /api/* is thin plumbing onto gui.app's pure functions;
/files/* serves generated .scad/.stl/preview-PNG output from this run's own
working directory (nothing outside it is ever reachable).
"""

from __future__ import annotations

import json
import mimetypes
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import app as gui_app

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PORT = 8420


def _make_handler(workdir: Path):
    counter_lock = threading.Lock()
    counter = {"n": 0}

    class Handler(BaseHTTPRequestHandler):
        server_version = "PolyForgeGUI/1"

        def log_message(self, fmt, *args):  # noqa: A003 - quieter default logging
            pass

        def _send_json(self, status: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path):
            if not path.is_file():
                self._send_json(404, {"error": f"not found: {path.name}"})
                return
            mime, _ = mimetypes.guess_type(str(path))
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self):  # noqa: N802 - http.server's naming convention
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/" or path == "/index.html":
                self._send_file(STATIC_DIR / "index.html")
                return

            if path == "/api/templates":
                self._send_json(200, gui_app.templates_json())
                return

            if path == "/api/ollama/status":
                qs = parse_qs(parsed.query)
                auto_start = qs.get("auto_start", ["0"])[0] == "1"
                self._send_json(200, gui_app.ollama_status_json(auto_start=auto_start))
                return

            if path.startswith("/files/"):
                requested = (workdir / path[len("/files/"):]).resolve()
                if workdir.resolve() not in requested.parents and requested != workdir.resolve():
                    self._send_json(403, {"error": "forbidden"})
                    return
                self._send_file(requested)
                return

            self._send_json(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            try:
                payload = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json(400, {"error": "malformed JSON body"})
                return

            try:
                if path == "/api/design":
                    with counter_lock:
                        counter["n"] += 1
                        next_id = counter["n"]
                    result = gui_app.design_json(payload, workdir, next_id)
                    self._send_json(200, result)
                elif path == "/api/preview":
                    result = gui_app.preview_json(payload.get("filename", ""), workdir)
                    self._send_json(200, result)
                elif path == "/api/export":
                    result = gui_app.export_json(payload.get("filename", ""), workdir)
                    self._send_json(200, result)
                else:
                    self._send_json(404, {"error": "not found"})
            except gui_app.DesignError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - never leak a bare stack trace to the browser
                self._send_json(500, {"error": f"internal error: {exc}"})

    return Handler


def find_free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def make_server(workdir: Path, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Build (but don't run) a bound, ready-to-serve HTTP server -- split out
    from `serve()` so tests can start it in a background thread and shut it
    down cleanly, instead of only being able to exercise the blocking
    Ctrl+C-driven loop."""
    workdir.mkdir(parents=True, exist_ok=True)
    actual_port = find_free_port(port)
    return ThreadingHTTPServer(("127.0.0.1", actual_port), _make_handler(workdir))


def serve(workdir: Path, port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    httpd = make_server(workdir, port)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"PolyForge GUI: {url}  (working directory: {workdir})")
    print("Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
