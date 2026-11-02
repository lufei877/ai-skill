import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sync import missing_knowledge_fields


class SkillInventoryTests(unittest.TestCase):
    def test_prose_listing_field_names_is_not_evidence_metadata(self):
        self.assertEqual(
            missing_knowledge_fields("步骤：填写 scope、evidence、verified_at、status。"),
            ["scope", "evidence", "verified_at", "status"],
        )

    def test_labeled_chinese_and_english_values_are_recognized(self):
        entry = "**范围**：project\n- `evidence`: regression test\n**日期**：2026-09-09\n- `status`: active\n"
        self.assertEqual(missing_knowledge_fields(entry), [])


if __name__ == "__main__":
    unittest.main()
