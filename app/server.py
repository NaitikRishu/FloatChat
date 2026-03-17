from __future__ import annotations

from contextlib import closing
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .database import connect
from .query_engine import dashboard_summary, map_payload, run_query


STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"


class OceanRequestHandler(BaseHTTPRequestHandler):
    db_path: Path
    openai_service: object | None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(
                {
                    "status": "ok",
                    "llm": self.openai_service.health_payload() if self.openai_service else None,
                }
            )
            return
        if parsed.path == "/api/summary":
            with closing(connect(self.db_path)) as connection:
                self._send_json(dashboard_summary(connection))
            return
        if parsed.path == "/api/map":
            with closing(connect(self.db_path)) as connection:
                self._send_json(map_payload(connection))
            return
        if parsed.path == "/":
            self._serve_static("index.html")
            return
        if parsed.path.startswith("/static/"):
            relative_path = parsed.path.removeprefix("/static/")
            self._serve_static(relative_path)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Route not found.")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND, "Route not found.")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        payload = json.loads(raw_body or "{}")
        question = str(payload.get("message", "")).strip()
        if not question:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing message field.")
            return

        lat = payload.get("lat")
        lon = payload.get("lon")
        selected_point = None
        if lat is not None and lon is not None:
            selected_point = (float(lat), float(lon))

        with closing(connect(self.db_path)) as connection:
            response = run_query(
                connection,
                question,
                selected_point=selected_point,
                openai_service=self.openai_service,
            )
        self._send_json(response)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_json(self, payload: dict) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content)

    def _serve_static(self, relative_path: str) -> None:
        target = (STATIC_ROOT / relative_path).resolve()
        if not str(target).startswith(str(STATIC_ROOT.resolve())) or not target.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Static file not found.")
            return
        content = target.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(target))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content)


def run_server(host: str, port: int, db_path: Path, openai_service: object | None = None) -> None:
    class BoundHandler(OceanRequestHandler):
        pass

    BoundHandler.db_path = db_path
    BoundHandler.openai_service = openai_service
    server = ThreadingHTTPServer((host, port), BoundHandler)
    print(f"ARGO Ocean Assistant running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ARGO Ocean Assistant...")
    finally:
        server.server_close()
