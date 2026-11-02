from __future__ import annotations

import http.client
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from governance_dashboard import DashboardServer


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.project = root / "app"
        self.project.mkdir()
        (self.project / "main.py").write_text("version = 1")
        (root / "governance").mkdir()
        (root / "governance/projects.json").write_text(json.dumps({"version": 1, "projects": [
            {"name": "app", "path": str(self.project), "enabled": True, "sync_approved": False},
        ]}))
        shutil.copytree(ROOT / "docs/governance-dashboard", root / "docs/governance-dashboard")
        self.server = DashboardServer(root, 0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, path: str, body: dict | None = None, **overrides) -> tuple[int, bytes]:
        headers = {"Origin": self.origin, "X-Cadence-Token": self.server.token, "Content-Type": "application/json"}
        headers.update(overrides)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request("GET" if body is None else "POST", path,
                               body=None if body is None else json.dumps(body), headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_settings_observe_and_reload_without_project_writes(self) -> None:
        status, payload = self.request("/api/state")
        self.assertEqual(status, 200)
        state = json.loads(payload)
        self.assertFalse(state["projects"][0]["selected"])
        body = {"project": "app", "revision": state["revision"],
                "policy": {"selected": True, "base_days": 1, "adaptive": False}}
        self.assertEqual(self.request("/api/settings", body)[0], 200)
        self.assertEqual(self.request("/api/settings", body)[0], 409)
        self.assertEqual(self.request("/api/observe", {})[0], 200)
        _, payload = self.request("/api/state")
        row = json.loads(payload)["projects"][0]
        self.assertTrue(row["due"])
        self.assertEqual(row["effective_days"], 1)
        self.assertEqual(list(self.project.iterdir()), [self.project / "main.py"])
        self.assertEqual((self.project / "main.py").read_text(), "version = 1")

    def test_external_origins_wrong_tokens_and_hosts_cannot_write(self) -> None:
        for headers in ({"Origin": "https://example.com"}, {"X-Cadence-Token": "wrong"}, {"Host": "example.com"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("/api/observe", {}, **headers)[0], 403)
        self.assertFalse(self.server.service.path.exists())
        self.assertEqual(self.request("/api/state", **{"Host": "example.com"})[0], 403)

    def test_assets_are_allowlisted_and_request_payload_bounded(self) -> None:
        for path in ("/", "/app.js", "/style.css"):
            self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request("/../governance/projects.json")[0], 404)
        self.assertEqual(self.request("/api/observe", {}, **{"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("/api/observe", {"padding": "a" * 9000})[0], 409)

    def test_known_connected_project_is_visible_before_registration(self) -> None:
        root = self.server.service.root
        other = root / "connected-app"
        marker = other / ".ai-skill/framework/RULES.md"
        marker.parent.mkdir(parents=True)
        marker.write_text("existing project framework")
        (root / "governance/known-projects.json").write_text(json.dumps({"version": 1, "projects": [
            {"label": "Connected app", "path": str(other)},
        ]}))
        before = (root / "governance/projects.json").read_bytes()
        status, payload = self.request("/api/state")
        self.assertEqual(status, 200)
        candidate = json.loads(payload)["discovery"]["projects"][0]
        self.assertEqual(candidate["path"], str(other))
        self.assertEqual(candidate["connection"]["skill"], "detected")
        self.assertEqual((root / "governance/projects.json").read_bytes(), before)
        self.assertFalse(self.server.service.path.exists())

    def test_explicit_registration_adds_visible_unselected_project_only(self) -> None:
        other = self.server.service.root / "new-app"
        other.mkdir()
        body = {"path": str(other), "name": "new-app"}
        self.assertEqual(self.request("/api/register", body)[0], 200)
        self.assertEqual(self.request("/api/register", body)[0], 200)
        _, payload = self.request("/api/state")
        rows = json.loads(payload)["projects"]
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[1]["selected"])
        self.assertFalse(rows[1]["sync_approved"])
        self.assertEqual(rows[1]["connection"]["skill"], "not_detected")
        self.assertEqual(list(other.iterdir()), [])
        self.assertEqual(self.request("/api/register", {"path": str(other), "name": "x"}, Origin="https://example.com")[0], 403)


if __name__ == "__main__":
    unittest.main()
