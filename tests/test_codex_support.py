from __future__ import annotations

import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from codex_support import (
    deploy_codex_project, detect_project, framework_files, merge_managed_block, native_skill_payloads,
    sync_project_skills,
    native_skill_catalog, project_skill_groups, select_project_skill_groups,
)

INIT_PROJECT_SPEC = importlib.util.spec_from_file_location(
    "ai_skill_init_project", SCRIPTS / "init-project.py"
)
assert INIT_PROJECT_SPEC and INIT_PROJECT_SPEC.loader
INIT_PROJECT = importlib.util.module_from_spec(INIT_PROJECT_SPEC)
INIT_PROJECT_SPEC.loader.exec_module(INIT_PROJECT)


class TtyStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


class CodexSupportTests(unittest.TestCase):
    def test_vscode_keeps_unparseable_or_nonobject_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            target = project / ".vscode/settings.json"
            target.parent.mkdir()
            for content in ('{\n // personal setting\n "editor.fontSize": 16,\n}', '[1, 2]', 'null'):
                with self.subTest(content=content):
                    target.write_text(content, encoding="utf-8")
                    original = target.read_bytes()
                    with self.assertRaisesRegex(ValueError, "preserved"):
                        INIT_PROJECT.generate_vscode(project)
                    self.assertEqual(target.read_bytes(), original)

    def test_vscode_preserves_existing_json_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            target = project / ".vscode/settings.json"
            target.parent.mkdir()
            target.write_text('{"editor.fontSize":16}', encoding="utf-8")
            INIT_PROJECT.generate_vscode(project)
            settings = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(settings["editor.fontSize"], 16)
            self.assertEqual(settings["ai-skill.rules"], "RULES.md")

    def test_explicit_workflow_keeps_three_part_contract_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(sys, "stdin", TtyStringIO()), mock.patch.object(sys, "stdout", TtyStringIO()):
                with mock.patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
                    choice = INIT_PROJECT.choose_workflow_integration(Path(temp), "enabled", "example")
            self.assertEqual(choice, ("enabled", "example", "flow-lite"))

    def test_standalone_framework_can_initialize_without_central_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "first"
            project.mkdir()
            deploy_codex_project(ROOT, project)
            framework = project / ".ai-skill/framework"
            destination = Path(temp) / "second"
            destination.mkdir()
            result = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(framework / "scripts/init-project.py"),
                 "--path", str(destination), "--ide", "codex",
                 "--conversation-archive", "off"],
                cwd=destination, capture_output=True, text=True, encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((destination / ".agents/skills/health/SKILL.md").is_file())
            self.assertFalse((destination / ".ai-skill/project/workflow-integration.json").exists())

    def test_invalid_explicit_workflow_options_fail_before_installing_files(self) -> None:
        for arguments in (
            ["--workflow-system-id", "example"],
            ["--workflow-integration", "enabled"],
            ["--workflow-integration", "enabled", "--workflow-system-id", "example",
             "--workflow-mode", "skill-only"],
        ):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as temp:
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", "-B", str(SCRIPTS / "init-project.py"),
                     "--path", temp, "--ide", "codex", "--conversation-archive", "off", *arguments],
                    capture_output=True, text=True, encoding="utf-8", check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_diagnostic_packages_keep_references_in_isolated_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            deploy_codex_project(ROOT, project)
            for name in ("hunt", "code-review", "skill-factory", "desktop-release"):
                package = project / ".agents/skills" / name
                self.assertTrue((package / "SKILL.md").is_file(), name)
                for document in package.rglob("*.md"):
                    for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                        if "://" in link or link.startswith("#"):
                            continue
                        target = (document.parent / link.split("#", 1)[0]).resolve()
                        self.assertTrue(target.is_relative_to(package.resolve()), link)
                        self.assertTrue(target.is_file(), f"{name}: {link}")
                self.assertTrue((package / "WAZA-LICENSE").is_file(), name)
            framework = project / ".ai-skill/framework"
            result = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(framework / "scripts/skill_factory.py"), "validate",
                 str(project / ".agents/skills/hunt")],
                cwd=project, capture_output=True, text=True, encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_deletion_of_managed_file_is_preserved_as_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            relative = Path("sample/SKILL.md")
            sync_project_skills(project, {relative: "v1"})
            target = project / ".agents/skills" / relative
            target.unlink()
            self.assertEqual(sync_project_skills(project, {relative: "v2"}), [relative.as_posix()])
            self.assertFalse(target.exists())

    def test_catalog_matches_compiler_and_records_sources(self) -> None:
        catalog = native_skill_catalog(ROOT)
        names = {entry["name"] for entry in catalog}
        self.assertEqual(names, {path.parts[0] for path in native_skill_payloads(ROOT) if path.name == "SKILL.md"})
        self.assertEqual(len(names), len(catalog))
        self.assertTrue(all((ROOT / entry["source"]).is_file() for entry in catalog))

    def test_new_project_installs_core_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            deploy_codex_project(ROOT, project)
            desktop_source = ROOT / "codex/skills/desktop-release"
            for source in desktop_source.rglob("*"):
                if source.is_file():
                    deployed = project / ".agents/skills/desktop-release" / source.relative_to(desktop_source)
                    self.assertEqual(
                        deployed.read_text(encoding="utf-8"),
                        source.read_text(encoding="utf-8"),
                    )
            self.assertEqual(project_skill_groups(project), ["core"])

    def test_deployed_framework_can_validate_its_full_source_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            deploy_codex_project(ROOT, project)
            framework = project / ".ai-skill/framework"
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(framework / "scripts/skill_factory.py"), "validate-library"],
                cwd=project, capture_output=True, text=True, encoding="utf-8", check=True,
            )
            self.assertIn(f"{len(native_skill_catalog(ROOT))} central skills; 0 errors", result.stdout)
            self.assertTrue((framework / "docs/skill-model-evaluation.md").is_file())
            self.assertTrue((framework / "evals/model-task-cases.json").is_file())

    def test_managed_upgrade_updates_clean_files_and_preserves_package_on_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            skill = Path("sample/SKILL.md")
            helper = Path("sample/references/contract.md")
            self.assertEqual(sync_project_skills(project, {skill: "v1", helper: "ref1"}), [])
            self.assertEqual(sync_project_skills(project, {skill: "v2", helper: "ref2"}), [])
            destination = project / ".agents/skills"
            (destination / helper).write_text("local", encoding="utf-8")
            self.assertEqual(sync_project_skills(project, {skill: "v3", helper: "ref3"}), [helper.as_posix()])
            self.assertEqual((destination / skill).read_text(encoding="utf-8"), "v2")
            self.assertEqual((destination / helper).read_text(encoding="utf-8"), "local")

    def test_legacy_snapshot_allows_only_unchanged_generated_skill_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / ".ai-skill/framework/skills/quality/testing.md"
            source.parent.mkdir(parents=True)
            source.write_text("---\nid: testing\ntitle: Testing\ntrigger: test\n---\n\nOld rules\n", encoding="utf-8")
            legacy = native_skill_payloads(project / ".ai-skill/framework")
            target = project / ".agents/skills/testing/SKILL.md"
            target.parent.mkdir(parents=True)
            target.write_text(legacy[Path("testing/SKILL.md")], encoding="utf-8")
            self.assertEqual(sync_project_skills(project, {Path("testing/SKILL.md"): "New rules\n"}), [])
            self.assertEqual(target.read_text(encoding="utf-8"), "New rules\n")

    def test_sync_preview_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.assertEqual(sync_project_skills(project, {Path("sample/SKILL.md"): "rules"}, dry_run=True), [])
            self.assertEqual(list(project.iterdir()), [])

    def test_first_deployment_preserves_unmanaged_same_name_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            target = project / ".agents/skills/code-review/SKILL.md"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"# Project review\nKeep local rules.\n")
            conflicts = deploy_codex_project(ROOT, project)
            self.assertEqual(target.read_bytes(), b"# Project review\nKeep local rules.\n")
            self.assertIn("code-review/SKILL.md", conflicts)

    def test_repeated_deployment_preserves_project_only_skill_without_managing_it(self) -> None:
        name = "desktop-ui-design"
        self.assertNotIn(name, {path.parts[0] for path in native_skill_payloads(ROOT)})
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            package = project / ".agents/skills" / name
            originals = {
                Path("SKILL.md"): b"# Project UI rules\r\nKeep local tokens.\r\n",
                Path("references/design.md"): "# 项目设计规范\n".encode("utf-8"),
            }
            for relative, content in originals.items():
                target = package / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)

            for _ in range(3):
                self.assertEqual(deploy_codex_project(ROOT, project), [])
                self.assertEqual(
                    {
                        path.relative_to(package): path.read_bytes()
                        for path in package.rglob("*") if path.is_file()
                    },
                    originals,
                )
                manifest = json.loads(
                    (project / ".ai-skill/project/managed-skills.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertIn("code-review/SKILL.md", manifest["files"])
                self.assertFalse(
                    any(Path(path).parts[0] == name for path in manifest["files"])
                )

    def test_repeated_deployment_preserves_local_edits_until_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            deploy_codex_project(ROOT, project)
            target = project / ".agents/skills/code-review/SKILL.md"
            target.write_text("# Local override\n", encoding="utf-8")
            for _ in range(2):
                conflicts = deploy_codex_project(ROOT, project)
                self.assertIn("code-review/SKILL.md", conflicts)
                self.assertEqual(target.read_text(encoding="utf-8"), "# Local override\n")
            target.write_text(native_skill_payloads(ROOT)[Path("code-review/SKILL.md")], encoding="utf-8")
            self.assertEqual(deploy_codex_project(ROOT, project), [])

    def test_interactive_first_connection_asks_for_archive_cadence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            stdin = TtyStringIO()
            stdout = TtyStringIO()
            with (
                mock.patch.object(INIT_PROJECT.sys, "stdin", stdin),
                mock.patch.object(INIT_PROJECT.sys, "stdout", stdout),
                mock.patch("builtins.input", return_value="3"),
            ):
                cadence = INIT_PROJECT.choose_conversation_archive_cadence(project, None)

        self.assertEqual(cadence, "daily")
        self.assertIn("首次接入需要选择会话归档频率", stdout.getvalue())

    def test_interactive_skill_connection_does_not_ask_for_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            stdin = TtyStringIO()
            stdout = TtyStringIO()
            with (
                mock.patch.object(INIT_PROJECT.sys, "stdin", stdin),
                mock.patch.object(INIT_PROJECT.sys, "stdout", stdout),
                mock.patch("builtins.input", side_effect=AssertionError("unexpected prompt")),
            ):
                choice = INIT_PROJECT.choose_workflow_integration(project, None, None)

        self.assertIsNone(choice)
        self.assertNotIn("是否将本项目加入整体工作流系统", stdout.getvalue())

    def test_managed_block_preserves_existing_agents_content(self) -> None:
        existing = "# Project Rules\n\nKeep this line.\n"
        first = merge_managed_block(existing, "# ai-skill\nfirst")
        second = merge_managed_block(first, "# ai-skill\nsecond")

        self.assertIn("Keep this line.", second)
        self.assertNotIn("first", second)
        self.assertEqual(second.count("<!-- ai-skill:start -->"), 1)
        self.assertEqual(second.count("<!-- ai-skill:end -->"), 1)

    def test_detect_project_uses_manifest_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "src").mkdir()
            (project / "src" / "main.tsx").write_text("export {};", encoding="utf-8")
            (project / "package.json").write_text(
                json.dumps(
                    {
                        "name": "sample-app",
                        "scripts": {"test": "vitest", "build": "vite build"},
                        "dependencies": {"react": "19.0.0", "electron": "38.0.0"},
                    }
                ),
                encoding="utf-8",
            )

            profile = detect_project(project)

        self.assertIn("sample-app", profile)
        self.assertIn("Electron", profile)
        self.assertIn("React", profile)
        self.assertIn("npm run test", profile)
        self.assertNotIn("{{", profile)

    def test_detected_md_issue_14_is_identical_across_git_paths_and_local_noise(self) -> None:
        for has_package in (False, True):
            with self.subTest(has_package=has_package), tempfile.TemporaryDirectory() as temp:
                first = Path(temp) / "original"
                second = Path(temp) / "different-worktree-name"
                first.mkdir()
                (first / "src").mkdir()
                (first / "src/main.ts").write_text("export {};\n", encoding="utf-8")
                (first / "中文目录").mkdir()
                (first / "中文目录/notes file.md").write_text("# Notes\n", encoding="utf-8")
                (first / ".gitignore").write_text(
                    "artifacts/\nsrc/cache/\n", encoding="utf-8"
                )
                if has_package:
                    (first / "package.json").write_text(
                        json.dumps({"name": "sample-app", "dependencies": {"react": "19.0.0"}}),
                        encoding="utf-8",
                    )
                subprocess.run(["git", "init", str(first)], check=True, capture_output=True)
                subprocess.run(["git", "-C", str(first), "add", "."], check=True, capture_output=True)
                subprocess.run(
                    ["git", "-C", str(first), "-c", "user.name=Test",
                     "-c", "user.email=test@example.invalid", "commit", "-m", "fixture"],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "clone", "--local", str(first), str(second)],
                    check=True, capture_output=True,
                )
                for relative in ("desktop-dist/local.py", "artifacts/local.rs", "src/cache/local.go"):
                    target = second / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("", encoding="utf-8")
                for name in ("pyproject.toml", "requirements-local.txt", "go.mod"):
                    (second / name).write_text("", encoding="utf-8")
                if not has_package:
                    (second / "package.json").write_text(
                        json.dumps({"name": "local-only", "scripts": {"build": "vite"}}),
                        encoding="utf-8",
                    )

                profiles = []
                for project in (first, second):
                    deploy_codex_project(ROOT, project)
                    profiles.append((project / ".ai-skill/project/detected.md").read_bytes())

                self.assertEqual(profiles[0], profiles[1])
                profile = profiles[0].decode("utf-8").replace("\r\n", "\n")
                self.assertIn("- 项目路径: 仓库根目录\n", profile)
                self.assertIn("- 语言: JavaScript/TypeScript\n", profile)
                self.assertIn("- 顶层业务目录: src, 中文目录\n", profile)
                if has_package:
                    self.assertIn("- 项目名称: sample-app\n", profile)
                    self.assertIn("- 框架: React\n", profile)
                else:
                    self.assertIn("- 项目名称: 未识别\n", profile)
                    self.assertIn("- 框架: 未识别\n", profile)
                self.assertNotIn("local-only", profile)
                self.assertNotIn("npm run build", profile)
                for project in (first, second):
                    self.assertNotIn(str(project), profile)

    def test_detect_project_issue_14_keeps_non_git_directory_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "plain-project"
            (project / "business").mkdir(parents=True)
            (project / "business/main.py").write_text("", encoding="utf-8")
            (project / "pyproject.toml").write_text("", encoding="utf-8")

            profile = detect_project(project)

            self.assertIn("- 项目名称: plain-project\n", profile)
            self.assertIn("- 项目路径: 仓库根目录\n", profile)
            self.assertIn("- 语言: Python\n", profile)
            self.assertIn("- 框架: Python project\n", profile)
            self.assertIn("- 顶层业务目录: business\n", profile)
            self.assertIn("- test: `python -m pytest`", profile)

    def test_detect_project_issue_14_keeps_tracked_manifest_detection(self) -> None:
        for manifest, language, command in (
            ("pyproject.toml", "Python", "python -m pytest"),
            ("requirements-dev.txt", "Python", "python -m pytest"),
            ("go.mod", "Go", "go test ./..."),
        ):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                (project / manifest).write_text("", encoding="utf-8")
                subprocess.run(
                    ["git", "init", str(project)], check=True, capture_output=True
                )
                subprocess.run(
                    ["git", "-C", str(project), "add", manifest],
                    check=True, capture_output=True,
                )

                profile = detect_project(project)

                self.assertIn(f"- 语言: {language}\n", profile)
                self.assertIn(f"- test: `{command}`", profile)

    def test_native_payloads_include_entry_and_common_skills(self) -> None:
        payloads = native_skill_payloads(ROOT)
        expected = {
            Path("ai-skill-bootstrap/SKILL.md"),
            Path("conversation-archive/SKILL.md"),
            Path("project-knowledge-evolution/SKILL.md"),
            Path("desktop-operations-architecture/SKILL.md"),
            Path("verification-evidence-ladder/SKILL.md"),
            Path("flow/SKILL.md"),
        }
        self.assertTrue(expected.issubset(payloads))

    def test_distribution_excludes_templates_workflows_and_python_cache(self) -> None:
        payload_paths = set(native_skill_payloads(ROOT))
        framework_paths = {
            path.relative_to(ROOT)
            for path in framework_files(ROOT)
        }

        for path in payload_paths | framework_paths:
            self.assertNotEqual(path.name, "_template.md")
            self.assertNotEqual(path.suffix, ".pyc")
            self.assertFalse(
                {"__pycache__", "history", "snapshots", "workflows"}.intersection(path.parts)
            )

    def test_plugin_exposes_only_lightweight_entry_skills(self) -> None:
        plugin_skills = ROOT / "codex" / "plugins" / "ai-skill-governance" / "skills"
        names = {path.name for path in plugin_skills.iterdir() if path.is_dir()}
        self.assertEqual(
            names,
            {
                "ai-skill-bootstrap",
                "conversation-archive",
                "project-knowledge-evolution",
                "flow",
                "skill-factory",
                "health",
                "hunt",
            },
        )

    def test_codex_initializer_is_idempotent_and_preserves_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "AGENTS.md").write_text("# Existing\n\nKeep me.\n", encoding="utf-8")
            knowledge = project / ".ai-skill" / "project" / "knowledge" / "pitfalls.md"
            knowledge.parent.mkdir(parents=True)
            knowledge.write_text("# Existing pitfall\n", encoding="utf-8")
            (project / "main.py").write_text("print('ok')\n", encoding="utf-8")

            command = [
                sys.executable,
                str(SCRIPTS / "init-project.py"),
                "--path",
                str(project),
                "--ide",
                "codex",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run(command, check=True, capture_output=True, text=True)

            agents = (project / "AGENTS.md").read_text(encoding="utf-8")
            preserved = knowledge.read_text(encoding="utf-8")

            self.assertIn("Keep me.", agents)
            self.assertEqual(agents.count("<!-- ai-skill:start -->"), 1)
            self.assertEqual(preserved, "# Existing pitfall\n")
            self.assertTrue(
                (project / ".agents" / "skills" / "project-knowledge-evolution" / "SKILL.md").exists()
            )
            self.assertTrue((project / ".ai-skill" / "framework" / "RULES.md").exists())
            self.assertFalse(
                (project / ".ai-skill" / "project" / "conversation-archive.json").exists()
            )
            self.assertFalse(
                (project / ".ai-skill" / "project" / "workflow-integration.json").exists()
            )
            detected = (project / ".ai-skill" / "project" / "detected.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Python", detected)
            self.assertNotIn("{{", detected)

    def test_initializer_records_first_archive_choice_and_preserves_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "main.py").write_text("print('ok')\n", encoding="utf-8")
            command = [
                sys.executable,
                str(SCRIPTS / "init-project.py"),
                "--path",
                str(project),
                "--ide",
                "codex",
                "--conversation-archive",
                "daily",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            policy_path = (
                project / ".ai-skill" / "project" / "conversation-archive.json"
            )
            first = json.loads(policy_path.read_text(encoding="utf-8"))

            command[-1] = "off"
            subprocess.run(command, check=True, capture_output=True, text=True)
            second = json.loads(policy_path.read_text(encoding="utf-8"))

        self.assertEqual(first["cadence"], "daily")
        self.assertEqual(second, first)

    def test_initializer_records_workflow_choice_and_preserves_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "main.py").write_text("print('ok')\n", encoding="utf-8")
            command = [
                sys.executable,
                str(SCRIPTS / "init-project.py"),
                "--path",
                str(project),
                "--ide",
                "codex",
                "--workflow-integration",
                "enabled",
                "--workflow-system-id",
                "xiaohongshu-content",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            policy_path = project / ".ai-skill" / "project" / "workflow-integration.json"
            first = json.loads(policy_path.read_text(encoding="utf-8"))

            command[-4:] = ["--workflow-integration", "disabled"]
            subprocess.run(command, check=True, capture_output=True, text=True)
            second = json.loads(policy_path.read_text(encoding="utf-8"))

        self.assertEqual(first["enabled"], True)
        self.assertEqual(first["system_id"], "xiaohongshu-content")
        self.assertEqual(first["mode"], "flow-lite")
        self.assertEqual(first["routing"], "project")
        self.assertEqual(second, first)

    def test_initializer_records_requested_workflow_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            command = [
                sys.executable,
                str(SCRIPTS / "init-project.py"),
                "--path",
                str(project),
                "--ide",
                "codex",
                "--workflow-integration",
                "enabled",
                "--workflow-system-id",
                "xiaohongshu-content",
                "--workflow-mode",
                "flow-standard",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            policy = json.loads(
                (project / ".ai-skill" / "project" / "workflow-integration.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(policy["mode"], "flow-standard")

    def test_initializer_records_explicit_disabled_workflow_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            command = [
                sys.executable,
                str(SCRIPTS / "init-project.py"),
                "--path",
                str(project),
                "--ide",
                "codex",
                "--workflow-integration",
                "disabled",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            policy = json.loads(
                (project / ".ai-skill" / "project" / "workflow-integration.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(policy["enabled"], False)
        self.assertIsNone(policy["system_id"])
        self.assertEqual(policy["mode"], "skill-only")


if __name__ == "__main__":
    unittest.main()
