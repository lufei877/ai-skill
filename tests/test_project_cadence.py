from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from project_cadence import CadenceService, choose_interval

NOW = datetime(2026, 9, 9, 4, tzinfo=timezone.utc)


class CadenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "app"
        self.project.mkdir()
        (self.project / "main.py").write_text("version = 1\n")
        (self.root / "governance").mkdir()
        (self.root / "governance/projects.json").write_text(json.dumps({"version": 1, "projects": [
            {"name": "app", "path": str(self.project), "enabled": True, "sync_approved": False},
        ]}))
        self.service = CadenceService(self.root, machine="test-host")

    def select(self, **kwargs) -> None:
        self.service.configure("app", {"selected": True, "base_days": 7, "adaptive": True, **kwargs}, revision=0, now=NOW)

    def test_first_scan_is_baseline_not_activity_or_automatic_selection(self) -> None:
        row = self.service.tick(NOW)["projects"][0]
        self.assertFalse(row["selected"])
        self.assertEqual(row["events_48h"], 0)
        self.assertFalse(row["due"])

    def test_busy_project_accelerates_and_duplicate_scan_does_not_inflate(self) -> None:
        self.select()
        self.service.tick(NOW)
        for index, hours in enumerate((3, 25, 28)):
            (self.project / "main.py").write_text(f"version = {index+2}\n")
            board = self.service.tick(NOW + timedelta(hours=hours))
        row = board["projects"][0]
        self.assertEqual(row["effective_days"], 1)
        self.assertEqual(row["events_48h"], 3)
        self.assertEqual(self.service.tick(NOW + timedelta(hours=28))["projects"][0]["events_48h"], 3)

    def test_fourteen_observed_inactive_days_cools_but_missing_gap_does_not(self) -> None:
        self.select(base_days=1)
        for day in range(15):
            row = self.service.tick(NOW + timedelta(days=day))["projects"][0]
        self.assertEqual(row["effective_days"], 7)
        self.assertIn("14", row["reason"])

    def test_sampling_gap_is_not_evidence_of_inactivity(self) -> None:
        self.select(base_days=1)
        self.service.tick(NOW)
        row = self.service.tick(NOW + timedelta(days=15))["projects"][0]
        self.assertEqual(row["effective_days"], 1)

    def test_daily_sampler_can_accelerate_after_two_active_days(self) -> None:
        self.select()
        self.service.tick(NOW)
        for day in (1, 2):
            (self.project / "main.py").write_text(str(day))
            row = self.service.tick(NOW + timedelta(days=day))["projects"][0]
        self.assertEqual(row["effective_days"], 1)

    def test_knowledge_maintenance_alone_does_not_keep_project_hot(self) -> None:
        self.select(base_days=1)
        target = self.project / ".ai-skill/project/evolution/log.md"
        target.parent.mkdir(parents=True)
        for day in range(15):
            target.write_text(f"Maintenance report {day}")
            row = self.service.tick(NOW + timedelta(days=day))["projects"][0]
        self.assertEqual(row["effective_days"], 7)
        self.assertGreater(row["knowledge_changes_48h"], 0)

    def test_stale_observation_cannot_be_claimed(self) -> None:
        self.select()
        self.service.tick(NOW)
        later = NOW + timedelta(hours=37)
        self.assertEqual(self.service.board(later)["projects"][0]["availability"], "stale")
        with self.assertRaises(ValueError):
            self.service.claim("app", later)

    def test_expired_worker_cannot_overwrite_new_claim(self) -> None:
        self.select()
        self.service.tick(NOW)
        old = self.service.claim("app", NOW)
        later = NOW + timedelta(hours=7)
        new = self.service.claim("app", later)
        report = self.root / "report.md"
        report.write_text("Late old worker")
        with self.assertRaises(ValueError):
            self.service.complete("app", old["run_id"], "completed", report, later)
        self.assertEqual(self.service.board(later)["projects"][0]["active_run"]["run_id"], new["run_id"])

    def test_overlapping_write_is_rejected_without_losing_state(self) -> None:
        self.select()
        with self.service.write():
            with self.assertRaises(ValueError):
                self.service.tick(NOW)
        self.assertTrue(self.service.board(NOW)["projects"][0]["selected"])

    def test_corrupt_state_is_not_silently_reset(self) -> None:
        self.service.path.parent.mkdir(parents=True)
        self.service.path.write_text("{broken")
        with self.assertRaises(ValueError):
            self.service.tick(NOW)
        self.assertEqual(self.service.path.read_text(), "{broken")

    def test_manual_fixed_frequency_is_respected(self) -> None:
        self.select(adaptive=False)
        self.service.tick(NOW)
        for hour in (2, 25, 28):
            (self.project / "main.py").write_text(str(hour))
            row = self.service.tick(NOW + timedelta(hours=hour))["projects"][0]
        self.assertEqual(row["effective_days"], 7)

    def test_completion_requires_claim_and_evidence_and_no_change_is_valid(self) -> None:
        self.select()
        board = self.service.tick(NOW)
        self.assertTrue(board["projects"][0]["due"])
        job = self.service.claim("app", NOW)
        with self.assertRaises(ValueError):
            self.service.claim("app", NOW)
        with self.assertRaises(ValueError):
            self.service.complete("app", job["run_id"], "no_change", self.root / "missing", NOW)
        report = self.root / "report.md"
        report.write_text("Reviewed changes: no durable knowledge.\n")
        self.service.complete("app", job["run_id"], "no_change", report, NOW)
        row = self.service.board(NOW)["projects"][0]
        self.assertFalse(row["due"])
        self.assertEqual(row["last_result"], "no_change")

    def test_change_during_work_remains_pending(self) -> None:
        self.select(base_days=1)
        self.service.tick(NOW)
        job = self.service.claim("app", NOW)
        (self.project / "main.py").write_text("new concurrent change")
        self.service.tick(NOW + timedelta(hours=1))
        report = self.root / "report.md"
        report.write_text("Reviewed original snapshot")
        self.service.complete("app", job["run_id"], "completed", report, NOW + timedelta(hours=2))
        self.assertTrue(self.service.board(NOW + timedelta(hours=2))["projects"][0]["pending_changes"])

    def test_stale_settings_do_not_overwrite(self) -> None:
        self.select()
        with self.assertRaises(ValueError):
            self.service.configure("app", {"selected": False, "base_days": 7, "adaptive": False}, revision=0)
        self.assertTrue(self.service.board(NOW)["projects"][0]["selected"])

    def test_build_outputs_and_generated_framework_do_not_count_as_activity(self) -> None:
        self.select()
        self.service.tick(NOW)
        for relative in ("dist/main.py", ".ai-skill/framework/RULES.md", ".agents/skills/testing/SKILL.md"):
            target = self.project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("generated")
        self.assertEqual(self.service.tick(NOW + timedelta(hours=1))["projects"][0]["events_48h"], 0)

    def test_nested_electron_package_does_not_block_source_observation(self) -> None:
        self.service.tick(NOW)
        output = self.project / "package-verify/win-unpacked/LICENSES.chromium.html"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
        row = self.service.tick(NOW + timedelta(hours=1))["projects"][0]
        self.assertEqual(row["availability"], "available")
        self.assertEqual(row["events_48h"], 0)

    def test_missing_project_does_not_cool_and_failed_run_does_not_complete(self) -> None:
        self.select(base_days=1)
        self.service.tick(NOW)
        job = self.service.claim("app", NOW)
        report = self.root / "failed.md"
        report.write_text("Read failed")
        self.service.complete("app", job["run_id"], "failed", report, NOW)
        self.project.rename(self.root / "moved")
        row = self.service.tick(NOW + timedelta(days=20))["projects"][0]
        self.assertEqual(row["effective_days"], 1)
        self.assertEqual(row["availability"], "missing")
        self.assertIsNone(row["last_completed_at"])


if __name__ == "__main__":
    unittest.main()


class MultiMachineCadenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "app"
        self.project.mkdir()
        (self.project / "main.py").write_text("version = 1\n")
        (self.root / "governance").mkdir()
        foreign = "/srv/remote/app" if sys.platform == "win32" else "D:\\remote\\app"
        (self.root / "governance/projects.json").write_text(json.dumps({"version": 1, "projects": [
            {"name": "app", "path": str(self.project), "enabled": True, "sync_approved": False},
            {"name": "remote", "path": foreign, "enabled": True, "sync_approved": False},
        ]}))
        self.legacy = {"name": "remote", "policy": {"selected": True, "base_days": 2, "adaptive": False},
                       "state": {"files": {"a.py": "x"}, "last_completed_at": NOW.isoformat()}}
        (self.root / "governance/cadence.json").write_text(json.dumps({
            "version": 1, "revision": 4, "last_tick_at": None,
            "projects": {"remote": {"policy": self.legacy["policy"], "state": self.legacy["state"]}}}))

    def test_machines_keep_separate_files_and_legacy_is_untouched(self) -> None:
        before = (self.root / "governance/cadence.json").read_bytes()
        one = CadenceService(self.root, machine="linux-a")
        two = CadenceService(self.root, machine="linux-b")
        one.tick(NOW)
        two.tick(NOW + timedelta(hours=1))
        self.assertNotEqual(one.path, two.path)
        self.assertTrue(one.path.exists() and two.path.exists())
        self.assertEqual((self.root / "governance/cadence.json").read_bytes(), before)

    def test_foreign_project_is_not_observed_or_reset(self) -> None:
        service = CadenceService(self.root, machine="linux-a")
        board = service.tick(NOW)
        remote = next(row for row in board["projects"] if row["name"] == "remote")
        self.assertEqual(remote["availability"], "not_local")
        self.assertFalse(remote["due"])
        self.assertNotIn("remote", json.loads(service.path.read_text())["projects"])

    def test_machine_owning_legacy_project_inherits_its_state(self) -> None:
        local_remote = self.root / "remote-here"
        local_remote.mkdir()
        registry = json.loads((self.root / "governance/projects.json").read_text())
        registry["projects"][1]["path"] = str(local_remote)
        (self.root / "governance/projects.json").write_text(json.dumps(registry))
        service = CadenceService(self.root, machine="windows-a")
        data = service.read()
        self.assertEqual(data["projects"]["remote"]["policy"], self.legacy["policy"])
        self.assertEqual(data["projects"]["remote"]["state"]["last_completed_at"], NOW.isoformat())
