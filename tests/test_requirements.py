from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync import discover_all_skills, generate_index
from validate_requirements import (
    EVIDENCE_NOTICE, REQUIRED_SECTIONS, validate_document, validate_library,
)


class RequirementsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.card = "# 虚构需求卡\n\n" + EVIDENCE_NOTICE + "\n\n" + "\n\n".join(
            f"## {section}\n\n虚构场景说明。" for section in REQUIRED_SECTIONS
        )

    def test_repository_requirements_pass_structure_and_credential_scan(self) -> None:
        self.assertEqual(validate_library(ROOT / "requirements"), [])

    def test_template_has_all_eight_sections_and_fixed_evidence_notice(self) -> None:
        content = (ROOT / "requirements/_template.md").read_text(encoding="utf-8")
        self.assertEqual(
            re.findall(r"^## (.+)$", content, re.MULTILINE),
            ["要解决的问题", "已确认的行为", "验收标准", "已知的坑",
             "参考实现", "测试模板", "与项目无关化", "待确认"],
        )
        self.assertIn(EVIDENCE_NOTICE, content)

    def test_each_missing_section_is_rejected_even_when_mentioned_in_prose(self) -> None:
        for section in REQUIRED_SECTIONS:
            with self.subTest(section=section):
                content = self.card.replace(f"## {section}\n", f"正文提到{section}\n")
                self.assertIn(
                    f"sample-card.md: missing section: {section}",
                    validate_document("sample-card.md", content),
                )

    def test_card_without_fixed_evidence_notice_is_rejected(self) -> None:
        errors = validate_document("sample-card.md", self.card.replace(EVIDENCE_NOTICE, ""))
        self.assertIn("sample-card.md: missing fixed evidence notice", errors)

    def test_english_kebab_case_names_are_required_except_template_and_readme(self) -> None:
        for name in ("sample-card.md", "chrome-cdp-v2.md", "_template.md"):
            with self.subTest(name=name):
                self.assertEqual(validate_document(name, self.card), [])
        for name in ("SampleCard.md", "sample_card.md", "卡密登录.md", "sample--card.md"):
            with self.subTest(name=name):
                self.assertTrue(any("filename" in error for error in validate_document(name, self.card)))
        self.assertEqual(validate_document("README.md", "# 索引\n"), [])

    def test_missing_library_cannot_pass_vacuously(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(validate_library(Path(temp)), [
                "README.md: required file missing",
                "_template.md: required file missing",
            ])

    def test_all_markdown_cards_are_validated_and_readme_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "README.md").write_text("# 索引\n", encoding="utf-8")
            (directory / "_template.md").write_text(self.card, encoding="utf-8")
            (directory / "sample-card.md").write_text(self.card, encoding="utf-8")
            self.assertEqual(validate_library(directory), [])
            (directory / "broken-card.md").write_text("# 缺章节\n", encoding="utf-8")
            (directory / "README.md").write_text(
                "cookie = <synthetic-value>\n", encoding="utf-8"
            )
            errors = validate_library(directory)
            self.assertIn("broken-card.md: missing section: 测试模板", errors)
            self.assertIn("README.md:1: suspected credential", errors)

    def test_credential_assignments_are_rejected_without_echoing_values(self) -> None:
        # Synthetic markers only; these are never usable credentials.
        for assignment in (
            'token: "<synthetic-value>"', '"access_token": "<synthetic-value>"',
            "PASSWORD=<synthetic-value>", "Cookie: <synthetic-value>",
            "`api_key` = <synthetic-value>", "client-secret: <synthetic-value>",
            "密码：<synthetic-value>", "-----BEGIN RSA PRIVATE KEY-----",
        ):
            with self.subTest(assignment=assignment):
                errors = validate_document("sample-card.md", self.card + "\n" + assignment)
                self.assertEqual(len(errors), 1)
                self.assertIn("suspected credential", errors[0])
                self.assertNotIn("<synthetic-value>", "\n".join(errors))

    def test_credential_policy_mentions_are_not_assignments(self) -> None:
        content = self.card + "\n禁止密码、Cookie、token、密钥与真实数据。\n"
        self.assertEqual(validate_document("sample-card.md", content), [])

    def test_cli_passes_without_modifying_requirement_files(self) -> None:
        directory = ROOT / "requirements"
        before = {path.name: path.read_bytes() for path in directory.glob("*.md")}
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "scripts/validate_requirements.py")],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            {path.name: path.read_bytes() for path in directory.glob("*.md")}, before
        )

    def test_index_generator_preserves_requirement_entry_without_counting_it_as_skill(self) -> None:
        skills = discover_all_skills()
        index = generate_index(skills)
        self.assertEqual((ROOT / "INDEX.md").read_text(encoding="utf-8"), index)
        self.assertIn("[requirements/README.md](requirements/README.md)", index)
        self.assertIn("用需求库里的卡密登录", index)
        self.assertIn(f"共 {len(skills)} 个中央原生 Skill", index)
        self.assertNotIn("requirements", {skill["name"] for skill in skills})

    def test_router_row_maps_requirement_requests_to_name_matching_index(self) -> None:
        router = (ROOT / "router.md").read_text(encoding="utf-8")
        row = next(line for line in router.splitlines() if line.startswith("| 需求库复用 |"))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        for phrase in ("需求库", "用需求库里的 X", "用需求库里的卡密登录"):
            self.assertIn(phrase, cells[1])
        self.assertIn("[requirements/README.md](requirements/README.md)", cells[2])
        self.assertIn("按卡片中文名称或英文文件名匹配", cells[2])
        self.assertIn("未匹配时报告尚未入库", router)
        self.assertIn("多张匹配时请用户选择", router)

    def test_readme_index_links_exist_and_list_every_central_card(self) -> None:
        directory = ROOT / "requirements"
        readme = (directory / "README.md").read_text(encoding="utf-8")
        self.assertIn("| 卡片 | 覆盖范围 | 状态 |", readme)
        rows = [line for line in readme.splitlines() if line.startswith("| [")]
        linked = set()
        for row in rows:
            match = re.search(r"\]\(([^)]+\.md)\)", row)
            self.assertIsNotNone(match, row)
            name = match.group(1)
            self.assertTrue((directory / name).is_file(), name)
            self.assertEqual(len(row.strip("|").split("|")), 3)
            linked.add(name)
        self.assertEqual(linked, {
            path.name for path in directory.glob("*.md") if path.name != "README.md"
        })
        self.assertIn("当前尚无中央需求卡", readme)
        self.assertIn("「卡密登录」属于尚未入库", readme)


if __name__ == "__main__":
    unittest.main()
