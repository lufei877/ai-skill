from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "codex/skills/health/scripts/collect_health.py"
SPEC = importlib.util.spec_from_file_location("collect_health", SCRIPT)
assert SPEC and SPEC.loader
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


class HealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_toml_trust_matches_escaped_and_literal_windows_paths(self) -> None:
        for header in ['[projects."D:\\\\Work\\\\Demo"]',
                       "[projects.'D:\\Work\\Demo']"]:
            with self.subTest(header=header):
                path = self.write("config.toml", header + '\ntrust_level = "trusted"\n')
                result = health.codex_config(path, "d:/Work/demo", "global")
                self.assertEqual(result["project_trust"], "trusted")

    def test_trust_absent_conflicting_and_parent_entries_are_distinct(self) -> None:
        path = self.write("config.toml", '[projects."D:/repo"]\ntrust_level="trusted"\n')
        result = health.codex_config(path, "D:/repo/sub", "global")
        self.assertEqual(result["project_trust"], "no_exact_entry")
        path.write_text('[projects."D:/repo"]\ntrust_level="trusted"\n'
                        '[projects."d:/REPO"]\ntrust_level="untrusted"\n', encoding="utf-8")
        self.assertEqual(health.codex_config(path, "D:/repo", "global")["project_trust"], "conflicting_entries")

    def test_instruction_mentions_and_examples_do_not_prove_delegation(self) -> None:
        path = self.write("CLAUDE.md", "OpenAI Codex: 读 AGENTS.md (简版)\n```\n@AGENTS.md\n```\n")
        self.assertEqual(health.instruction(path, "project")["agents_reference"], "mention_only")
        path.write_text("@AGENTS.md\n", encoding="utf-8")
        self.assertEqual(health.instruction(path, "project")["agents_reference"], "explicit_import_signal")

    def test_managed_block_requires_unique_ordered_markers(self) -> None:
        path = self.write("AGENTS.md", "<!-- ai-skill:end -->\n<!-- ai-skill:start -->")
        self.assertEqual(health.instruction(path, "project")["managed_block"], "malformed")
        path.write_text("<!-- ai-skill:start -->\nrule\n<!-- ai-skill:end -->", encoding="utf-8")
        self.assertEqual(health.instruction(path, "project")["managed_block"], "present")

    def test_nested_skill_collisions_and_overlapping_roots(self) -> None:
        text = '---\nname: demo\ndescription: Example\n---\nRule\n'
        self.write("skills/demo/SKILL.md", text)
        self.write("skills/bundle/sub/demo/SKILL.md", text + "Different\n")
        result = health.skill_inventory([self.root / "skills", self.root / "skills/bundle"])
        self.assertEqual(result["unique_packages"], 2)
        self.assertEqual(len(result["duplicate_candidates"]), 1)
        self.assertEqual(result["duplicate_candidates"][0]["content"], "different")
        self.assertEqual(len(result["duplicate_candidates"][0]["paths"]), 2)
        self.assertEqual(result["activation"], "unverified")

    def test_skill_scan_reports_budget_limit(self) -> None:
        self.write("skills/demo/SKILL.md", '---\nname: demo\n---\n')
        result = health.skill_inventory([self.root / "skills"], max_directories=1)
        self.assertEqual(result["roots"][0]["status"], "partial")

    def test_skill_symlink_alias_is_not_a_second_package(self) -> None:
        path = self.write("skills/demo/SKILL.md", '---\nname: demo\n---\n')
        alias = self.root / "alias"
        try:
            alias.symlink_to(path.parent, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlink creation unavailable")
        result = health.skill_inventory([self.root / "skills", alias])
        self.assertEqual(result["unique_packages"], 1)
        self.assertEqual(result["duplicate_candidates"], [])

    def test_sensitive_config_values_and_parser_errors_are_not_printed(self) -> None:
        secret = "DO_NOT_OUTPUT_secret_123"
        path = self.write("config.toml", '[mcp_servers.local]\ncommand="python"\n'
                          f'args=["{secret}"]\n[mcp_servers.local.env]\nTOKEN="{secret}"\n'
                          f'[mcp_servers.remote]\nurl="https://{secret}.example/?key={secret}"\n')
        with mock.patch.object(health.shutil, "which", return_value=sys.executable):
            result = health.codex_config(path, str(self.root), "global")
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result["mcp"][0]["runtime"], "unverified")
        path.write_text(f'token = "{secret}', encoding="utf-8")
        result = health.codex_config(path, str(self.root), "global")
        self.assertEqual(result["status"], "invalid")
        self.assertNotIn(secret, json.dumps(result))

    def test_mcp_missing_disabled_and_relative_paths_are_not_live_failures(self) -> None:
        path = self.write("config.toml", '[mcp_servers.off]\nenabled=false\ncommand="missing"\n'
                          f'[mcp_servers.broken]\ncommand={json.dumps(str(self.root / "absent.exe"))}\n'
                          '[mcp_servers.relative]\ncommand="./server.exe"\n')
        servers = {item["name"]: item for item in health.codex_config(path, str(self.root), "project")["mcp"]}
        self.assertEqual(servers["off"]["state"], "disabled")
        self.assertEqual(servers["broken"]["executable"], "missing")
        self.assertEqual(servers["relative"]["executable"], "relative_unverified")
        self.assertTrue(all(s["runtime"] == "unverified" for s in servers.values()))

    def test_unc_executable_is_not_probed_over_the_network(self) -> None:
        with mock.patch.object(Path, "is_file", side_effect=AssertionError("Unexpected filesystem probe")):
            result = health.mcp_summary({"remote_share": {"command": r"\\server\share\mcp.exe"}})
        self.assertEqual(result[0]["executable"], "network_path_unverified")

    def test_json_settings_emit_metadata_without_sensitive_values(self) -> None:
        secret = "DO_NOT_OUTPUT_fixture_secret"
        path = self.write("settings.json", json.dumps({
            "env": {"TOKEN": secret}, "hooks": {"PreToolUse": [{"command": secret}]},
            "permissions": {"allow": [secret]},
            "mcpServers": {"remote": {"url": secret, "headers": {"Authorization": secret}}},
        }))
        result = health.json_config(path, "project")
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result["hook_event_count"], 1)
        self.assertEqual(result["permission_entry_counts"]["allow"], 1)

    def test_claude_settings_do_not_masquerade_as_an_mcp_config(self) -> None:
        path = self.write("settings.json", '{"mcpServers":{"misplaced":{"command":"python"}}}')
        result = health.json_config(path, "project")
        self.assertEqual(result["mcp"], [])
        self.assertTrue(result["misplaced_mcp_servers"])

    def test_claude_user_config_only_collects_current_project_mcp(self) -> None:
        path = self.write(".claude.json", json.dumps({
            "mcpServers": {"user_server": {"url": "private"}},
            "projects": {
                str(self.root): {"mcpServers": {"project_server": {"command": "python"}}},
                str(self.root / "other"): {"mcpServers": {"UNRELATED_PRIVATE": {"command": "python"}}},
            },
        }))
        result = health.json_config(path, "global", str(self.root))
        self.assertEqual(result["mcp"][0]["name"], "user_server")
        self.assertEqual(result["project_mcp"][0]["mcp"][0]["name"], "project_server")
        self.assertEqual(result["project_mcp"][0]["scope"], "project")
        self.assertNotIn("UNRELATED_PRIVATE", json.dumps(result))

    def test_oversized_and_malformed_files_are_coverage_gaps(self) -> None:
        path = self.write("config.toml", "x" * (health.MAX_BYTES + 1))
        result = health.codex_config(path, str(self.root), "project")
        self.assertEqual(result["status"], "too_large")
        self.assertEqual(result["project_trust"], "unverified")
        self.write("skills/broken/SKILL.md", "Not a valid skill")
        result = health.skill_inventory([self.root / "skills"])
        self.assertEqual(result["roots"][0]["status"], "partial")
        self.assertEqual(result["roots"][0]["gaps"][0]["reason"], "unsupported_or_missing_name")

    def test_project_only_cli_is_utf8_read_only_and_never_executes_config(self) -> None:
        project = self.root / "中文项目"
        project.mkdir()
        self.write("中文项目/AGENTS.md", "中文规则\n")
        self.write("中文项目/.mcp.json", json.dumps({"mcpServers": {"danger": {
            "command": sys.executable, "args": ["-c", "raise SystemExit('MUST_NOT_RUN')"]}}}))
        self.write("中文项目/package.json", json.dumps({"scripts": {
            "test": "MUST_NOT_RUN", "test:release:list": "node release.js --list-stages"}}))
        before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPT), str(project), "--project-only"],
                                capture_output=True, env={**os.environ, "PYTHONIOENCODING": "ascii"}, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        report = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(report["project"], str(project.resolve()))
        self.assertEqual(report["verifiers"]["executed"], False)
        commands = {item["name"]: item for item in report["verifiers"]["scripts"]}
        self.assertEqual(commands["test:release:list"]["kind"], "listing_hint")
        self.assertEqual(commands["test"]["kind"], "declared_command")
        self.assertNotIn("MUST_NOT_RUN", result.stdout.decode("utf-8"))
        self.assertEqual(before, {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()})
        self.assertTrue(all(item["scope"] == "project" for item in report["configs"]))


if __name__ == "__main__":
    unittest.main()
