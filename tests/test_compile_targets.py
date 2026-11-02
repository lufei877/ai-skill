import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CompileTargetsTests(unittest.TestCase):
    def test_issue_12_text_inputs_are_checked_out_with_lf(self):
        # Digests intentionally use LF content; checkout consistency belongs to .gitattributes.
        paths = (
            "CLAUDE.md",
            "codex/plugins/ai-skill-governance/.codex-plugin/plugin.json",
            "codex/plugins/ai-skill-governance/assets/framework/RULES.md",
        )
        for path in paths:
            with self.subTest(path=path):
                result = subprocess.run(
                    ["git", "check-attr", "eol", "--", path],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                )
                self.assertEqual(result.stdout.strip(), f"{path}: eol: lf")

    def test_flow_contract_requires_output_validation_and_semantic_failure_propagation(self):
        for path in (
            ROOT / "commands" / "flow.md",
            ROOT / ".agents" / "skills" / "flow" / "SKILL.md",
        ):
            content = path.read_text(encoding="utf-8")
            self.assertIn("Definition 声明的输出契约", content)
            self.assertIn("`status=failed`", content)
            self.assertIn("步骤和 Run 必须失败", content)

    def test_check_detects_skill_factory_framework_drift(self):
        mirrored_script = (
            ROOT
            / "codex"
            / "plugins"
            / "ai-skill-governance"
            / "assets"
            / "framework"
            / "scripts"
            / "skill_factory.py"
        )
        original = mirrored_script.read_bytes()
        try:
            mirrored_script.write_bytes(original + b"\n# intentional test drift\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "compile-targets.py"), "--check"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(Path("framework/scripts/skill_factory.py")), result.stdout)
        finally:
            mirrored_script.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
