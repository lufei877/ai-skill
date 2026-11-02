from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from library_release import (
    capture_release, export_release, promote_release, release_digest,
    require_stable_source, rollback_release, verify_release,
)


class LibraryReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "core").mkdir()
        (self.root / "evals").mkdir()
        (self.root / "RULES.md").write_text("# Core\nKeep scope.\n", encoding="utf-8")
        (self.root / "router.md").write_text("# Router\n", encoding="utf-8")
        self.write("core/behavior-contract.json", {
            "version": 1,
            "invariants": [{"id": "scope", "path": "RULES.md", "required": "Keep scope."}],
        })
        self.write("evals/core-behavior-cases.json", {
            "version": 1,
            "cases": [{"id": "small-edit", "prompt": "Fix typo", "kind": "execution",
                       "fixture": "evals/fixtures/core/app.py", "acceptance": "Only fix typo."}],
        })
        (self.root / "evals/fixtures/core").mkdir(parents=True)
        (self.root / "evals/fixtures/core/app.py").write_text("label = 'Saev'\n", encoding="utf-8")

    def write(self, path: str, data: dict) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")
        return target

    def review(self, rid: str, parent: str | None = None) -> Path:
        manifest, source = verify_release(self.root, rid)
        trace = self.root / f"{rid}-trace.txt"
        trace.write_text("Synthetic unit-test evidence, not a real model run.\n", encoding="utf-8")
        runs = [{"case_id": "small-edit", "variant": "candidate", "source_digest": manifest["digest"],
                 "model": "fixture-model", "reasoning": "fixture", "run_id": rid + "-candidate",
                 "executor": "fixture-executor", "reviewer": "fixture-reviewer", "outcome_passed": True,
                 "unnecessary_questions": 0, "unauthorized_actions": 0, "evidence_path": str(trace)}]
        if parent:
            runs.append({**runs[0], "variant": "baseline", "run_id": rid + "-baseline",
                         "source_digest": verify_release(self.root, parent)[0]["digest"]})
        return self.write(f"{rid}-review.json", {
            "source_digest": manifest["digest"],
            "suite_digest": release_digest({"suite": (source / "evals/core-behavior-cases.json").read_bytes().hex()}),
            "reviewer": "fixture-reviewer", "reviewed_paths": sorted(manifest["files"]),
            "core_review": {"scope": True},
            "checks": [{"name": name, "passed": True, "command": "fixture test",
                        "evidence_path": str(trace)} for name in ("regression", "contracts", "compilation", "index")],
            "runs": runs,
        })

    def test_unreviewed_source_cannot_distribute_or_promote(self) -> None:
        with self.assertRaises(ValueError):
            require_stable_source(self.root)
        capture_release(self.root, "v1", expected_parent=None)
        with self.assertRaises((ValueError, FileNotFoundError)):
            promote_release(self.root, "v1", self.root / "missing.json", expected_parent=None)
        with self.assertRaises(ValueError):
            require_stable_source(self.root)

    def test_promoted_snapshot_and_stale_working_source(self) -> None:
        capture_release(self.root, "v1", expected_parent=None)
        promote_release(self.root, "v1", self.review("v1"), expected_parent=None)
        self.assertEqual(require_stable_source(self.root).name, "source")
        (self.root / "RULES.md").write_text("# Core\nKeep scope.\nNew rule.\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            require_stable_source(self.root)

    def test_missing_principle_and_changed_tests_cannot_silently_pass(self) -> None:
        (self.root / "RULES.md").write_text("# Core\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            capture_release(self.root, "broken", expected_parent=None)
        (self.root / "RULES.md").write_text("# Core\nKeep scope.\n", encoding="utf-8")
        capture_release(self.root, "v1", expected_parent=None)
        promote_release(self.root, "v1", self.review("v1"), expected_parent=None)
        suite = self.root / "evals/core-behavior-cases.json"
        data = json.loads(suite.read_text())
        data["cases"][0]["acceptance"] = "Anything is fine."
        self.write("evals/core-behavior-cases.json", data)
        with self.assertRaises(ValueError):
            capture_release(self.root, "weaker", expected_parent="v1")

    def test_corrupt_snapshot_cannot_be_exported(self) -> None:
        capture_release(self.root, "v1", expected_parent=None)
        _, source = verify_release(self.root, "v1")
        (source / "RULES.md").write_text("tampered", encoding="utf-8")
        with self.assertRaises(ValueError):
            export_release(self.root, "v1", self.root / "recovered")
        self.assertFalse((self.root / "recovered").exists())

    def test_evidence_must_be_complete_independent_and_bound(self) -> None:
        capture_release(self.root, "v1", expected_parent=None)
        for field, value in (("source_digest", "old"), ("runs", []), ("core_review", {}),
                             ("reviewed_paths", []), ("checks", [])):
            report = self.review("v1")
            data = json.loads(report.read_text())
            data[field] = value
            report.write_text(json.dumps(data))
            with self.assertRaises(ValueError, msg=field):
                promote_release(self.root, "v1", report, expected_parent=None)
        report = self.review("v1")
        data = json.loads(report.read_text())
        data["runs"][0]["reviewer"] = "fixture-executor"
        report.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            promote_release(self.root, "v1", report, expected_parent=None)

    def test_stale_parallel_promotion_and_rollback_preserve_working_files(self) -> None:
        capture_release(self.root, "v1", expected_parent=None)
        capture_release(self.root, "parallel", expected_parent=None)
        promote_release(self.root, "v1", self.review("v1"), expected_parent=None)
        with self.assertRaises(ValueError):
            promote_release(self.root, "parallel", self.review("parallel"), expected_parent=None)
        capture_release(self.root, "v2", expected_parent="v1")
        promote_release(self.root, "v2", self.review("v2", "v1"), expected_parent="v1")
        before = (self.root / "RULES.md").read_bytes()
        rollback_release(self.root, "v1", expected_parent="v2")
        self.assertEqual((self.root / "RULES.md").read_bytes(), before)
        self.assertEqual(require_stable_source(self.root).parent.name, "v1")
        export_release(self.root, "v1", self.root / "restored")
        self.assertEqual((self.root / "restored/RULES.md").read_bytes(), before)

    def test_release_id_and_export_path_cannot_escape(self) -> None:
        for rid in ("../escape", "C:/escape", "v1/../../escape"):
            with self.assertRaises(ValueError):
                capture_release(self.root, rid, expected_parent=None)
        capture_release(self.root, "v1", expected_parent=None)
        with self.assertRaises(ValueError):
            export_release(self.root, "v1", self.root)

    def test_verified_release_syncs_without_original_external_evidence(self) -> None:
        from project_governance import sync_projects

        capture_release(self.root, "v1", expected_parent=None)
        report = self.review("v1")
        promote_release(self.root, "v1", report, expected_parent=None)
        report.unlink()
        (self.root / "v1-trace.txt").unlink()
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            registry = self.write("registry.json", {"version": 1, "projects": [
                {"name": "test", "path": str(project), "sync_approved": True},
            ]})
            result = sync_projects(self.root, registry, dry_run=False)
            self.assertEqual(result.projects[0].status, "synced")
            self.assertEqual((project / ".ai-skill/framework/RULES.md").read_text(), "# Core\nKeep scope.\n")

    def test_corrupt_archived_evidence_blocks_distribution(self) -> None:
        capture_release(self.root, "v1", expected_parent=None)
        promote_release(self.root, "v1", self.review("v1"), expected_parent=None)
        evidence = self.root / ".ai-skill/library-releases/v1/evidence/0.txt"
        evidence.write_text("modified")
        with self.assertRaises(ValueError):
            require_stable_source(self.root)

    def test_failed_behavior_or_missing_baseline_blocks_promotion(self) -> None:
        capture_release(self.root, "v1", expected_parent=None)
        report = self.review("v1")
        data = json.loads(report.read_text())
        data["runs"][0]["unnecessary_questions"] = 1
        report.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            promote_release(self.root, "v1", report, expected_parent=None)
        promote_release(self.root, "v1", self.review("v1"), expected_parent=None)
        capture_release(self.root, "v2", expected_parent="v1")
        with self.assertRaises(ValueError):
            promote_release(self.root, "v2", self.review("v2"), expected_parent="v1")

    def test_release_lock_and_source_changes_fail_without_valid_manifest(self) -> None:
        from unittest import mock
        from library_release import source_content

        store = self.root / ".ai-skill/library-releases"
        store.mkdir(parents=True)
        (store / "operation.lock").write_text("another owner")
        with self.assertRaises(ValueError):
            capture_release(self.root, "locked", expected_parent=None)
        self.assertEqual((store / "operation.lock").read_text(), "another owner")
        (store / "operation.lock").unlink()
        original = source_content(self.root)
        with mock.patch("library_release.source_content", side_effect=[original, {**original, "new.md": b"new"}]):
            with self.assertRaises(ValueError):
                capture_release(self.root, "changing", expected_parent=None)
        self.assertFalse((store / "changing/manifest.json").exists())

    def test_snapshot_preserves_non_python_and_binary_fixture_inputs(self) -> None:
        for name, content in (("parse.cjs", b"module.exports = {};"), ("input.bin", b"\x00\xff\x10")):
            (self.root / "evals/fixtures/core" / name).write_bytes(content)
        capture_release(self.root, "v1", expected_parent=None)
        _, source = verify_release(self.root, "v1")
        self.assertEqual((source / "evals/fixtures/core/input.bin").read_bytes(), b"\x00\xff\x10")
        self.assertTrue((source / "evals/fixtures/core/parse.cjs").is_file())

    def test_snapshot_preserves_authored_skill_licenses_and_assets(self) -> None:
        package = self.root / "codex/skills/example"
        for relative, content in (
            ("LICENSE", b"MIT notice"),
            ("CODE-AUDIT-LICENSE", b"Adapted MIT notice"),
            ("assets/sample.bin", b"\x00\xff"),
            ("scripts/helper.py", b"print('helper')"),
            ("scripts/__pycache__/helper.pyc", b"cache"),
        ):
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        capture_release(self.root, "package", expected_parent=None)
        _, source = verify_release(self.root, "package")
        self.assertEqual((source / "codex/skills/example/LICENSE").read_bytes(), b"MIT notice")
        self.assertEqual((source / "codex/skills/example/CODE-AUDIT-LICENSE").read_bytes(), b"Adapted MIT notice")
        self.assertEqual((source / "codex/skills/example/assets/sample.bin").read_bytes(), b"\x00\xff")
        self.assertFalse((source / "codex/skills/example/scripts/__pycache__/helper.pyc").exists())

    def test_source_digest_ignores_test_and_analysis_caches(self) -> None:
        from library_release import source_content

        original = source_content(self.root)
        for directory in (".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__"):
            path = self.root / "tests" / directory / "README.md"
            path.parent.mkdir(parents=True)
            path.write_text("Disposable tool cache", encoding="utf-8")
        self.assertEqual(source_content(self.root), original)

    def test_snapshot_preserves_authored_plugin_entrypoints_without_generated_copies(self) -> None:
        from library_release import source_content

        entries = (
            "codex/.agents/plugins/marketplace.json",
            "codex/plugins/ai-skill-governance/.codex-plugin/plugin.json",
        )
        for relative in entries:
            self.write(relative, {"name": "example"})
        self.write("codex/plugins/ai-skill-governance/assets/framework/copied.json", {"generated": True})
        capture_release(self.root, "entrypoints", expected_parent=None)
        _, source = verify_release(self.root, "entrypoints")
        for relative in entries:
            self.assertEqual((source / relative).read_bytes(), (self.root / relative).read_bytes())
        self.assertNotIn("codex/plugins/ai-skill-governance/assets/framework/copied.json", source_content(self.root))


if __name__ == "__main__":
    unittest.main()
