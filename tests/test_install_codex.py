import importlib.util
import json
import tempfile
import unittest
import sys
from types import SimpleNamespace
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "install_codex",
    ROOT / "scripts" / "install-codex.py",
)
assert SPEC is not None and SPEC.loader is not None
INSTALL_CODEX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL_CODEX)


class InstallCodexTests(unittest.TestCase):
    def test_install_rejects_stale_or_disabled_host_version(self):
        for version, enabled in (("1.0.0+old", True), ("1.0.0+new", False)):
            with self.subTest(version=version, enabled=enabled):
                response = {"installed": [{
                    "pluginId": "ai-skill-governance@ai-skill-local",
                    "version": version, "enabled": enabled,
                }]}
                with (
                    mock.patch.object(INSTALL_CODEX, "run"),
                    mock.patch.object(INSTALL_CODEX, "codex_command", return_value=["codex"]),
                    mock.patch.object(INSTALL_CODEX, "update_plugin_cachebuster", return_value="1.0.0+new"),
                    mock.patch.object(INSTALL_CODEX.subprocess, "run", side_effect=[
                        SimpleNamespace(stdout="ai-skill-local"),
                        SimpleNamespace(stdout=json.dumps(response)),
                    ]),
                ):
                    with self.assertRaisesRegex(RuntimeError, "expected enabled plugin version"):
                        INSTALL_CODEX.main()

    def test_plugin_version_is_stable_for_same_content_and_changes_with_resources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = Path(temp_dir)
            manifest = plugin_root / ".codex-plugin" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "name": "example",
                        "version": "1.2.3+codex.20260101000000",
                        "skills": "./skills/",
                    }
                ),
                encoding="utf-8",
            )

            resource = plugin_root / "skills/example/references/rules.md"
            resource.parent.mkdir(parents=True)
            resource.write_text("first rules", encoding="utf-8")
            version = INSTALL_CODEX.update_plugin_cachebuster(plugin_root)

            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertRegex(version, r"^1\.2\.3\+codex\.[0-9a-f]{16}$")
            self.assertEqual(payload["version"], version)
            self.assertEqual(payload["name"], "example")
            self.assertEqual(payload["skills"], "./skills/")
            self.assertEqual(INSTALL_CODEX.update_plugin_cachebuster(plugin_root), version)
            resource.write_text("second rules", encoding="utf-8")
            self.assertNotEqual(INSTALL_CODEX.update_plugin_cachebuster(plugin_root), version)

    def test_plugin_version_ignores_interpreter_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            plugin = Path(temp)
            manifest = plugin / ".codex-plugin/plugin.json"
            manifest.parent.mkdir()
            manifest.write_text('{"name":"test","version":"1.0.0"}', encoding="utf-8")
            version = INSTALL_CODEX.update_plugin_cachebuster(plugin)
            cache = plugin / "__pycache__/test.pyc"
            cache.parent.mkdir()
            cache.write_bytes(b"cache")
            self.assertEqual(INSTALL_CODEX.update_plugin_cachebuster(plugin), version)


if __name__ == "__main__":
    unittest.main()
