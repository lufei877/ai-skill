from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_registry import discover_known, integration_status, register_project


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "governance").mkdir()
        self.registry = self.root / "governance/projects.json"
        self.registry.write_text(json.dumps({"version": 1, "projects": [], "custom": "preserve"}))
        self.project = self.root / "project"
        self.project.mkdir()

    def known(self, projects: list) -> None:
        (self.root / "governance/known-projects.json").write_text(json.dumps({"version": 1, "projects": projects}))

    def test_registration_is_idempotent_by_resolved_path_and_preserves_policies(self) -> None:
        register_project(self.root, str(self.project), "one")
        data = json.loads(self.registry.read_text())
        data["projects"][0].update(enabled=False, sync_approved=True, audit_globs=["custom.md"])
        self.registry.write_text(json.dumps(data))
        before = self.registry.read_bytes()
        result = register_project(self.root, str(self.project / "../project"), "renamed")
        self.assertFalse(result["created"])
        self.assertEqual(result["name"], "one")
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_invalid_paths_and_name_collision_leave_registry_untouched(self) -> None:
        register_project(self.root, str(self.project), "one")
        other = self.root / "other"
        other.mkdir()
        before = self.registry.read_bytes()
        for path, name in (("relative/path", "two"), (str(self.root), "two"),
                           (str(self.root / "missing"), "two"), (str(other), "one")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                register_project(self.root, path, name)
        self.assertEqual(self.registry.read_bytes(), before)

    def test_registration_lock_rejects_overlapping_writer(self) -> None:
        self.registry.with_suffix(".lock").write_text("pid=example")
        with self.assertRaises(ValueError):
            register_project(self.root, str(self.project))
        self.assertEqual(json.loads(self.registry.read_text())["projects"], [])

    def test_only_explicit_known_roots_are_checked_and_registered_paths_deduplicated(self) -> None:
        marker = self.project / ".ai-skill/framework/RULES.md"
        marker.parent.mkdir(parents=True)
        marker.write_text("framework")
        unlisted = self.root / "unlisted/.ai-skill/framework/RULES.md"
        unlisted.parent.mkdir(parents=True)
        unlisted.write_text("framework")
        self.known([{"path": str(self.project), "label": "Known"}, {"path": str(self.project / "../project")}])
        result = discover_known(self.root)
        self.assertEqual(len(result["projects"]), 1)
        self.assertEqual(result["projects"][0]["name"], "Known")
        register_project(self.root, str(self.project))
        self.assertEqual(discover_known(self.root)["projects"], [])

    def test_workflow_only_is_not_reported_as_skill_installed(self) -> None:
        marker = self.project / ".ai-skill/project/workflow-integration.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({"version": 1, "enabled": True}))
        self.known([{"path": str(self.project)}])
        row = discover_known(self.root)["projects"][0]
        self.assertEqual(row["connection"]["workflow"], "enabled")
        self.assertEqual(row["connection"]["skill"], "not_detected")
        marker.write_text("broken json")
        state = integration_status(self.project)
        self.assertEqual(state["workflow"], "unknown")
        self.assertIsNotNone(state["error"])

    def test_absent_missing_and_unconnected_projects_do_not_invent_candidates(self) -> None:
        self.assertEqual(discover_known(self.root)["known_count"], 0)
        self.known([{"path": str(self.project)}, {"path": str(self.root / "missing")}])
        result = discover_known(self.root)
        self.assertEqual(result["projects"], [])
        self.assertEqual(len(result["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
