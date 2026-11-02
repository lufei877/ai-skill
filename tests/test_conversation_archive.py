from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "codex"
    / "skills"
    / "conversation-archive"
    / "scripts"
    / "archive_conversation.py"
)


class ConversationArchiveTests(unittest.TestCase):
    def test_documented_due_command_resolves_from_an_unrelated_directory(self) -> None:
        skill = SCRIPT.parent.parent
        documentation = (skill / "SKILL.md").read_text(encoding="utf-8")
        command_path = re.search(
            r'python -X utf8 -B "([^"]+)" due --project', documentation
        )
        self.assertIsNotNone(command_path, "Use an explicit package-relative absolute command")
        assert command_path is not None
        script = command_path.group(1).replace("<archive-skill>", str(skill))
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, "-X", "utf8", "-B", script, "due", "--project", temp],
                cwd=temp, capture_output=True, text=True, encoding="utf-8", check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["due"])

    def run_script(
        self,
        *arguments: str,
        input_payload: dict | None = None,
        input_text: str | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        stdin = input_text
        if stdin is None and input_payload is not None:
            stdin = json.dumps(input_payload, ensure_ascii=False)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=check,
        )

    def test_missing_policy_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_script("due", "--project", temp, "--date", "2026-08-07")

        payload = json.loads(result.stdout)
        self.assertFalse(payload["due"])
        self.assertEqual(payload["reason"], "policy-missing")

    def test_daily_record_is_redacted_idempotent_and_updates_due(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.run_script("configure", "--project", temp, "--cadence", "daily")
            before = json.loads(
                self.run_script("due", "--project", temp, "--date", "2026-08-07").stdout
            )
            summary = {
                "session_id": "019fda35-43a2-7900-9789-2cef14f2917b",
                "date": "2026-08-07",
                "transcript_path": "C:\\Users\\user\\.codex\\session.jsonl",
                "goals": ["Archive this project conversation"],
                "confirmed_facts": ["token=super-secret-value"],
                "decisions": ["Raw transcripts stay outside the project"],
                "changed_files": ["codex/skills/conversation-archive/SKILL.md"],
                "unresolved_items": [],
                "next_steps": ["Open the next task from the summary"],
                "user_preferences": ["Prefer concise evidence-backed summaries"],
            }
            first = json.loads(
                self.run_script(
                    "record", "--project", temp, "--input", "-", input_payload=summary
                ).stdout
            )
            daily_file = Path(first["file"])
            first_content = daily_file.read_text(encoding="utf-8")
            first_index = Path(first["index"]).read_text(encoding="utf-8")
            second = json.loads(
                self.run_script(
                    "record", "--project", temp, "--input", "-", input_payload=summary
                ).stdout
            )
            after = json.loads(
                self.run_script("due", "--project", temp, "--date", "2026-08-07").stdout
            )

            self.assertTrue(before["due"])
            self.assertFalse(after["due"])
            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertEqual(daily_file.read_text(encoding="utf-8"), first_content)
            self.assertEqual(Path(first["index"]).read_text(encoding="utf-8"), first_index)
            self.assertEqual(first_content.count("conversation:019fda35"), 2)
            self.assertIn("token=[REDACTED]", first_content)
            self.assertNotIn("super-secret-value", first_content)
            policy = json.loads(
                (project / ".ai-skill" / "project" / "conversation-archive.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(policy["cadence"], "daily")

    def test_weekly_due_uses_iso_week(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.run_script("configure", "--project", temp, "--cadence", "weekly")
            summary = {
                "session_id": "session-1",
                "date": "2026-08-03",
                "goals": ["Weekly archive"],
            }
            self.run_script(
                "record", "--project", temp, "--input", "-", input_payload=summary
            )
            same_week = json.loads(
                self.run_script("due", "--project", temp, "--date", "2026-08-09").stdout
            )
            next_week = json.loads(
                self.run_script("due", "--project", temp, "--date", "2026-08-10").stdout
            )

        self.assertFalse(same_week["due"])
        self.assertTrue(next_week["due"])

    def test_output_directory_cannot_escape_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_script(
                "configure",
                "--project",
                temp,
                "--cadence",
                "daily",
                "--output-directory",
                "../outside",
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must stay inside the project", result.stderr)

    def test_raw_transcript_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.run_script("configure", "--project", temp, "--cadence", "manual")
            result = self.run_script(
                "record",
                "--project",
                temp,
                "--input",
                "-",
                input_payload={
                    "session_id": "session-raw",
                    "goals": ["Archive safely"],
                    "raw_transcript": "full private conversation",
                },
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Unsupported summary fields: raw_transcript", result.stderr)

    def test_record_accepts_utf8_bom_from_windows_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.run_script("configure", "--project", temp, "--cadence", "manual")
            raw = "\ufeff" + json.dumps(
                {"session_id": "session-bom", "goals": ["Accept a PowerShell pipeline"]},
                ensure_ascii=False,
            )
            result = self.run_script(
                "record", "--project", temp, "--input", "-", input_text=raw
            )

        self.assertTrue(json.loads(result.stdout)["recorded"])


if __name__ == "__main__":
    unittest.main()
