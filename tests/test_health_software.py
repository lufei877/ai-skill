from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "codex/skills/health/scripts/collect_software.py"
SPEC = importlib.util.spec_from_file_location("collect_software", SCRIPT)
assert SPEC and SPEC.loader
software = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(software)


class SoftwareInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_inventory_keeps_manifests_tests_and_unknown_languages_visible(self) -> None:
        self.write("src/中文.py", "def run():\n    return 1\n")
        self.write("tests/test_app.py", "assert 1 == 1\n")
        self.write("frontend/package.json", '{"scripts":{"test":"must_not_run"}}')
        self.write("src/new.lang", "unknown language")
        data = software.collect(self.root)
        files = {f["path"]: f for f in data["files"]}
        self.assertEqual(files["src/中文.py"]["lines"], 2)
        self.assertEqual(files["tests/test_app.py"]["role"], "test_candidate")
        self.assertEqual(files["frontend/package.json"]["kind"], "manifest")
        self.assertEqual(files["frontend/package.json"]["content_status"], "not_read")
        self.assertEqual(files["src/new.lang"]["kind"], "other")
        self.assertEqual(data["coverage"]["semantic_review"], "not_performed")

    def test_duplicates_are_exact_content_candidates_without_quality_scores(self) -> None:
        for name in ["src/a.py", "src/b.py"]:
            self.write(name, "def work():\n    return 17\n")
        self.write("src/c.py", "def work():\n    return 18\n")
        data = software.collect(self.root)
        self.assertEqual(data["duplicate_candidates"], [["src/a.py", "src/b.py"]])
        self.assertNotIn("score", data)
        self.assertNotIn("findings", data)

    def test_dependencies_generated_and_secret_files_are_not_read(self) -> None:
        self.write("node_modules/lib/a.py", "raise RuntimeError('dependency')")
        self.write(".venv312/app.py", "raise RuntimeError('venv')")
        self.write(".ai-skill/framework/rules.py", "raise RuntimeError('mirror')")
        self.write(".env", "TOKEN=DO_NOT_READ")
        self.write("app.min.js", "DO_NOT_READ")
        self.write(".github/workflows/check.yml", "name: check")
        with mock.patch.object(Path, "open", side_effect=AssertionError("Unwanted read")):
            data = software.collect(self.root)
        self.assertEqual([f["path"] for f in data["files"]], [".github/workflows/check.yml"])
        self.assertTrue(any(x["reason"] == "sensitive_name" for x in data["excluded"]))
        self.assertEqual(data["coverage"]["vulnerability_database"], "not_queried")

    def test_entry_and_byte_limits_never_report_full_coverage(self) -> None:
        for n in range(4):
            self.write(f"f{n}.py", "x = 1234\n")
        data = software.collect(self.root, max_entries=2)
        self.assertEqual(data["coverage"]["inventory"], "partial")
        self.assertEqual(data["coverage"]["truncated_reason"], "entry_budget")
        data = software.collect(self.root, max_total_bytes=8)
        self.assertTrue(all(f["content_status"] == "byte_budget" for f in data["files"]))
        self.assertEqual(data["coverage"]["source_read"], "partial")

    def test_invalid_encoding_and_read_error_are_explicit_gaps(self) -> None:
        self.write("app.py", "test").write_bytes(b"\xff\xfe\xfd")
        data = software.collect(self.root)
        self.assertEqual(data["files"][0]["content_status"], "non_utf8_or_binary")
        with mock.patch.object(Path, "open", side_effect=PermissionError("SECRET ERROR")):
            data = software.collect(self.root)
        self.assertEqual(data["files"][0]["content_status"], "unreadable")
        self.assertNotIn("SECRET ERROR", json.dumps(data))

    def test_external_resolved_paths_are_excluded_before_read(self) -> None:
        path = self.write("linked.py", "DO_NOT_READ")
        original = Path.resolve
        def resolve(candidate: Path, *args, **kwargs) -> Path:
            if candidate == path:
                return self.root.parent / "outside.py"
            return original(candidate, *args, **kwargs)
        with mock.patch.object(Path, "resolve", resolve):
            data = software.collect(self.root)
        self.assertEqual(data["files"], [])
        self.assertEqual(data["excluded"][0]["reason"], "outside_root")

    def test_explicit_exclusions_are_reported_and_do_not_hide_other_modules(self) -> None:
        self.write("vendor-copy/a.py", "x = 1")
        self.write("app/a.py", "x = 2")
        data = software.collect(self.root, excludes=["vendor-copy"])
        self.assertEqual([f["path"] for f in data["files"]], ["app/a.py"])
        self.assertEqual(data["excluded"][0]["reason"], "user_exclusion")

    def test_cli_is_utf8_read_only_and_never_imports_project_code(self) -> None:
        self.write("应用.py", "raise RuntimeError('MUST_NOT_EXECUTE_secret')\n")
        self.write("package.json", '{"scripts":{"test":"MUST_NOT_EXECUTE_secret"}}')
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), str(self.root)],
            capture_output=True, check=False,
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        data = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(data["project"], str(self.root.resolve()))
        self.assertNotIn("MUST_NOT_EXECUTE_secret", result.stdout.decode("utf-8"))
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_isolated_deployment_keeps_resources_and_runs_without_author_cwd(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        self.addCleanup(sys.path.remove, str(ROOT / "scripts"))
        from codex_support import deploy_codex_project

        project = self.root / "deployed"
        project.mkdir()
        deploy_codex_project(ROOT, project)
        package = project / ".agents/skills/health"
        source = ROOT / "codex/skills/health"
        for document in source.rglob("*"):
            if document.is_file() and "__pycache__" not in document.parts and document.suffix != ".pyc":
                target = package / document.relative_to(source)
                self.assertEqual(target.read_text(encoding="utf-8"), document.read_text(encoding="utf-8"))
        for document in package.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if "://" in link or link.startswith("#"):
                    continue
                target = (document.parent / link.split("#", 1)[0]).resolve()
                self.assertTrue(target.is_relative_to(package.resolve()), link)
                self.assertTrue(target.is_file(), link)
        self.assertTrue((package / "LICENSE").is_file())
        self.assertTrue((package / "CODE-AUDIT-LICENSE").is_file())
        self.assertFalse(list(package.rglob("*.pyc")))
        self.write("deployed/src/应用.py", "raise RuntimeError('MUST_NOT_RUN')\n")
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(package / "scripts/collect_software.py"), str(project)],
            cwd=project, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("src/应用.py", [item["path"] for item in data["files"]])
        self.assertEqual(data["coverage"]["semantic_review"], "not_performed")
        self.assertNotIn("MUST_NOT_RUN", result.stdout)


if __name__ == "__main__":
    unittest.main()
