from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from project_governance import (
    audit_projects,
    independent_evidence_count,
    load_registry,
    preview_projects,
    sync_projects,
)


FOREIGN = "/srv/remote/project" if sys.platform == "win32" else "D:\\remote\\project"


class ProjectGovernanceTests(unittest.TestCase):
    def test_unverified_central_source_is_blocked_before_project_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            project = root / "project"
            project.mkdir()
            registry = self.write_registry(root, [{"name": "local", "path": str(project), "sync_approved": True}])
            with self.assertRaises(ValueError):
                sync_projects(framework, registry, dry_run=False)
            self.assertFalse((project / ".agents").exists())

    @mock.patch("project_governance.require_stable_source", side_effect=lambda root: root)
    def test_sync_reports_conflict_and_preserves_project_override(self, _gate: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            project = root / "project"
            target = project / ".agents/skills/testing/SKILL.md"
            target.parent.mkdir(parents=True)
            target.write_text("Project override\n", encoding="utf-8")
            registry = self.write_registry(root, [{"name": "local", "path": str(project), "sync_approved": True}])
            for dry_run in (True, False, False):
                result = sync_projects(framework, registry, dry_run=dry_run)
                self.assertEqual(result.projects[0].status, "conflict")
                self.assertEqual(target.read_text(encoding="utf-8"), "Project override\n")

    def create_framework(self, root: Path) -> Path:
        framework = root / "framework"
        (framework / "core").mkdir(parents=True)
        (framework / "skills" / "quality").mkdir(parents=True)
        (framework / "commands").mkdir()
        (framework / "evolution").mkdir()
        (framework / "codex" / "skills").mkdir(parents=True)
        (framework / "RULES.md").write_text("# Central rules\n", encoding="utf-8")
        (framework / "router.md").write_text("# Router\n", encoding="utf-8")
        (framework / "core" / "principles.md").write_text(
            "# Principles\n", encoding="utf-8"
        )
        (framework / "skills" / "quality" / "testing.md").write_text(
            "---\n"
            "id: testing\n"
            "title: Testing\n"
            "trigger: test\n"
            "---\n\n"
            "# Testing\n",
            encoding="utf-8",
        )
        return framework

    def write_registry(self, root: Path, projects: list[dict[str, object]]) -> Path:
        registry = root / "projects.json"
        registry.write_text(
            json.dumps({"version": 1, "projects": projects}, ensure_ascii=False),
            encoding="utf-8",
        )
        return registry

    def test_single_project_change_creates_candidate_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            project = root / "project"
            knowledge = project / ".ai-skill" / "project" / "knowledge" / "pitfalls.md"
            knowledge.parent.mkdir(parents=True)
            knowledge.write_text("# Pitfalls\n", encoding="utf-8")
            registry = self.write_registry(
                root,
                [
                    {
                        "name": "one-project",
                        "path": str(project),
                        "enabled": True,
                        "sync_approved": False,
                        "audit_globs": [".ai-skill/project/**/*.md"],
                    }
                ],
            )
            state = root / "state.json"
            report = root / "latest.md"

            baseline = audit_projects(framework, registry, state, report)
            knowledge.write_text("# Pitfalls\n\nVerified fix.\n", encoding="utf-8")
            changed = audit_projects(framework, registry, state, report)

            self.assertEqual(baseline.projects[0].changed_files, ())
            self.assertEqual(
                changed.projects[0].changed_files,
                (".ai-skill/project/knowledge/pitfalls.md",),
            )
            self.assertEqual(changed.projects[0].candidate_confidence, "single-project")
            self.assertIn("单项目证据候选", report.read_text(encoding="utf-8"))

    @mock.patch("project_governance.require_stable_source", side_effect=lambda root: root)
    def test_sync_preserves_agents_content_and_project_knowledge(self, _gate: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            project = root / "project"
            project.mkdir()
            (project / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (project / "AGENTS.md").write_text("# Existing\n\nKeep me.\n", encoding="utf-8")
            knowledge = project / ".ai-skill" / "project" / "knowledge" / "pitfalls.md"
            knowledge.parent.mkdir(parents=True)
            knowledge.write_text("# Private knowledge\n", encoding="utf-8")
            registry = self.write_registry(
                root,
                [
                    {
                        "name": "approved",
                        "path": str(project),
                        "enabled": True,
                        "sync_approved": True,
                    }
                ],
            )

            preview = sync_projects(framework, registry, dry_run=True)
            synced = sync_projects(framework, registry, dry_run=False)

            self.assertEqual(preview.projects[0].status, "would-sync")
            self.assertEqual(synced.projects[0].status, "synced")
            self.assertEqual(knowledge.read_text(encoding="utf-8"), "# Private knowledge\n")
            agents = (project / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Keep me.", agents)
            self.assertEqual(agents.count("<!-- ai-skill:start -->"), 1)
            self.assertTrue((project / ".ai-skill" / "framework" / "RULES.md").exists())
            self.assertTrue((project / ".agents" / "skills" / "testing" / "SKILL.md").exists())

    @mock.patch("project_governance.require_stable_source", side_effect=lambda root: root)
    def test_sync_preserves_existing_agents_line_endings(self, _gate: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            project = root / "project"
            project.mkdir()
            original = b"# Existing\n\nKeep LF exactly.\n"
            (project / "AGENTS.md").write_bytes(original)
            registry = self.write_registry(
                root,
                [
                    {
                        "name": "approved",
                        "path": str(project),
                        "enabled": True,
                        "sync_approved": True,
                    }
                ],
            )

            sync_projects(framework, registry, dry_run=False)

            agents = (project / "AGENTS.md").read_bytes()
            self.assertTrue(agents.startswith(original.rstrip() + b"\n\n"))
            self.assertNotIn(b"\r\n", agents)

    def test_sync_skips_project_without_distribution_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            project = root / "project"
            project.mkdir()
            registry = self.write_registry(
                root,
                [
                    {
                        "name": "not-approved",
                        "path": str(project),
                        "enabled": True,
                        "sync_approved": False,
                    }
                ],
            )

            result = sync_projects(framework, registry, dry_run=False)

            self.assertEqual(result.projects[0].status, "skipped-not-approved")
            self.assertFalse((project / ".ai-skill" / "framework").exists())

    def test_missing_project_does_not_stop_other_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            existing = root / "existing"
            existing.mkdir()
            registry = self.write_registry(
                root,
                [
                    {"name": "missing", "path": str(root / "missing"), "enabled": True},
                    {"name": "existing", "path": str(existing), "enabled": True},
                ],
            )

            result = audit_projects(
                framework,
                registry,
                root / "state.json",
                root / "latest.md",
            )

            self.assertEqual(result.projects[0].status, "missing")
            self.assertEqual(result.projects[1].status, "baseline")


if __name__ == "__main__":
    unittest.main()


class MultiMachineGovernanceTests(unittest.TestCase):
    create_framework = ProjectGovernanceTests.create_framework
    write_registry = ProjectGovernanceTests.write_registry

    def knowledge_project(self, root: Path, name: str) -> Path:
        project = root / name
        knowledge = project / ".ai-skill" / "project" / "knowledge" / "pitfalls.md"
        knowledge.parent.mkdir(parents=True)
        knowledge.write_text(f"# {name}\n", encoding="utf-8")
        return project

    def test_foreign_os_path_is_skipped_and_its_state_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            local = self.knowledge_project(root, "local")
            registry = self.write_registry(root, [
                {"name": "local", "path": str(local)},
                {"name": "remote", "path": FOREIGN},
            ])
            state = root / "state.json"
            baseline = {"files": {"AGENTS.md": "abc"}}
            state.write_text(json.dumps({"version": 1, "projects": {"remote": baseline}}), encoding="utf-8")

            result = audit_projects(framework, registry, state, root / "latest.md", machine="m1")

            statuses = {project.name: project.status for project in result.projects}
            self.assertEqual(statuses["remote"], "not-local")
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["projects"]["remote"], baseline)
            remote = next(project for project in load_registry(registry) if project.name == "remote")
            self.assertFalse(remote.local)
            self.assertNotIn(str(root), str(remote.path))

    def test_alternating_machines_do_not_clear_each_other(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            one = self.knowledge_project(root, "one")
            two = self.knowledge_project(root, "two")
            registry = self.write_registry(root, [
                {"name": "one", "path": str(one)},
                {"name": "two", "path": str(two)},
            ])
            legacy = root / "legacy-state.json"
            legacy.write_text(json.dumps({"version": 1, "projects": {
                "one": {"files": {"old.md": "1"}}, "gone": {"files": {"x.md": "2"}}}}), encoding="utf-8")
            first, second = root / "state" / "m1.json", root / "state" / "m2.json"

            audit_projects(framework, registry, first, root / "r1.md", legacy_state_path=legacy, machine="m1")
            audit_projects(framework, registry, second, root / "r2.md", legacy_state_path=legacy, machine="m2")
            audit_projects(framework, registry, first, root / "r1.md", legacy_state_path=legacy, machine="m1")

            self.assertIn("one", json.loads(first.read_text(encoding="utf-8"))["projects"])
            self.assertIn("two", json.loads(second.read_text(encoding="utf-8"))["projects"])
            self.assertNotIn("gone", json.loads(first.read_text(encoding="utf-8"))["projects"])
            self.assertIn("gone", json.loads(legacy.read_text(encoding="utf-8"))["projects"])
            self.assertIn("`m1`", (root / "r1.md").read_text(encoding="utf-8"))

    def test_same_project_on_two_machines_counts_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = self.write_registry(root, [
                {"name": "app", "project_id": "app", "path": FOREIGN},
                {"name": "app-linux", "project_id": "app", "path": str(root)},
                {"name": "other", "path": str(root / "other")},
            ])
            projects = load_registry(registry)
            self.assertEqual(independent_evidence_count(projects, ["app", "app-linux"]), 1)
            self.assertEqual(independent_evidence_count(projects, ["app", "app-linux", "other"]), 2)

    def test_preview_reports_drift_without_writing_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            framework = self.create_framework(root)
            project = self.knowledge_project(root, "project")
            registry = self.write_registry(root, [{"name": "project", "path": str(project)}])
            before = sorted(path.relative_to(project) for path in project.rglob("*"))
            report = root / "preview.md"

            total = preview_projects(framework, registry, report, machine="m1")

            self.assertGreater(total, 0)
            self.assertIn("缺失", report.read_text(encoding="utf-8"))
            self.assertEqual(sorted(path.relative_to(project) for path in project.rglob("*")), before)
