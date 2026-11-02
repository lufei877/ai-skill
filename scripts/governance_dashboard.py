"""Local project cadence dashboard; external scheduling remains user-owned."""
from __future__ import annotations

import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from library_release import require_stable_source
from project_cadence import CadenceService, ROOT
from project_registry import discover_known, integration_status, register_project


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, root: Path, port: int):
        self.service = CadenceService(root)
        self.assets = root / "docs/governance-dashboard"
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), DashboardHandler)


class DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardServer
    timeout = 15

    def log_message(self, format: str, *args: object) -> None:
        # Request paths contain no credentials; retain ordinary local access logs.
        super().log_message(format, *args)

    def send(self, status: int, content: bytes, kind: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(content)

    def json(self, status: int, value: dict) -> None:
        self.send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def valid_host(self) -> bool:
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self) -> None:
        if not self.valid_host():
            self.json(403, {"error": "Invalid local host"})
            return
        path = urlparse(self.path).path
        try:
            if path == "/favicon.ico":
                self.send(204, b"", "image/x-icon")
                return
            if path == "/api/state":
                board = self.server.service.board()
                try:
                    board["discovery"] = discover_known(self.server.service.root)
                except (OSError, ValueError) as error:
                    board["discovery"] = {"projects": [], "known_count": 0, "imported_at": None,
                                          "source": "项目清单读取失败", "errors": [{"path": "", "error": str(error)}]}
                registry = self.server.service.registry()
                for project in board["projects"]:
                    project["connection"] = integration_status(Path(project["path"]))
                    project["sync_approved"] = registry[project["name"]].sync_approved
                board["csrf"] = self.server.token
                try:
                    require_stable_source(self.server.service.root)
                    board["release_gate"] = "已验证稳定版，可按授权分发"
                except (ValueError, OSError) as error:
                    board["release_gate"] = f"待验收，未允许稳定分发：{error}"
                self.json(200, board)
                return
            allowed = {"/": ("index.html", "text/html; charset=utf-8"),
                       "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                       "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in allowed:
                self.json(404, {"error": "Not found"})
                return
            filename, kind = allowed[path]
            self.send(200, (self.server.assets / filename).read_bytes(), kind)
        except (OSError, ValueError) as error:
            self.json(500, {"error": str(error)})

    def do_POST(self) -> None:
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if (not self.valid_host() or self.headers.get("Origin") != origin
                or not secrets.compare_digest(self.headers.get("X-Cadence-Token", ""), self.server.token)):
            self.json(403, {"error": "Local same-origin request required"})
            return
        if self.headers.get("Content-Type") != "application/json":
            self.json(415, {"error": "JSON required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("JSON object required")
            if self.path == "/api/settings":
                if set(data) != {"project", "policy", "revision"} or type(data["revision"]) is not int:
                    raise ValueError("Invalid settings request")
                self.server.service.configure(data["project"], data["policy"], revision=data["revision"])
                self.json(200, {"saved": True})
            elif self.path == "/api/observe":
                self.server.service.tick()
                self.json(200, {"observed": True})
            elif self.path == "/api/register":
                if set(data) != {"path", "name"}:
                    raise ValueError("需要项目路径和名称")
                self.json(200, register_project(self.server.service.root, data["path"], data["name"]))
            else:
                self.json(404, {"error": "Not found"})
        except (ValueError, OSError, KeyError, TypeError) as error:
            self.json(409, {"error": str(error)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    with DashboardServer(args.root.resolve(), args.port) as server:
        print(f"Project dashboard: http://127.0.0.1:{server.server_port}", flush=True)
        print("No scheduler created. Use project_cadence.py tick from your chosen schedule.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Dashboard stopped.")


if __name__ == "__main__":
    main()
