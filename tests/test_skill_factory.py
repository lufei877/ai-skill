import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from skill_factory import evaluate_triggers, scaffold, validate_skill, summarize_model_runs


class SkillFactoryTests(unittest.TestCase):
    def test_model_summary_requires_evidence_and_keeps_missing_metrics_unknown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            cases = target / "cases.json"
            cases.write_text(json.dumps({"variants": ["current-library"], "cases": [
                {"id": "one", "required_skills": ["testing"], "forbidden_skills": ["flow"]},
                {"id": "two", "required_skills": [], "forbidden_skills": []},
            ]}), encoding="utf-8")
            results = target / "results.json"
            run = {"case_id": "one", "variant": "current-library", "model": "test-model", "reasoning": "test",
                   "run_id": "fixture-run", "evidence_path": "trace.txt", "selected_skills": ["testing"],
                   "outcome_passed": True, "unnecessary_questions": 0, "unauthorized_actions": 0, "elapsed_ms": 1200}
            results.write_text(json.dumps({"runs": [run]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "evidence"):
                summarize_model_runs(cases, results)
            (target / "trace.txt").write_text("Synthetic unit-test fixture; not a real model run.\n", encoding="utf-8")
            summary = summarize_model_runs(cases, results)["groups"][0]
            self.assertEqual(summary["routing_passed"], 1)
            self.assertEqual(summary["missing_cases"], ["two"])
            self.assertIsNone(summary["median_input_tokens"])
            self.assertIsNone(summary["unnecessary_dependencies"])
            self.assertEqual(summary["unnecessary_dependencies_observations"], 0)
            self.assertIsNone(summary["median_changed_lines"])
            results.write_text(json.dumps({"runs": [run, run]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                summarize_model_runs(cases, results)

    def test_model_summary_aggregates_only_observed_complexity_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            cases = target / "cases.json"
            cases.write_text(json.dumps({"variants": ["current-library"], "cases": [
                {"id": "one", "required_skills": ["complexity-review"], "forbidden_skills": []},
            ]}), encoding="utf-8")
            (target / "trace-one.txt").write_text("Observed model run one.\n", encoding="utf-8")
            (target / "trace-two.txt").write_text("Observed model run two.\n", encoding="utf-8")
            base = {"case_id": "one", "variant": "current-library", "model": "test-model",
                    "reasoning": "test", "selected_skills": ["complexity-review"],
                    "outcome_passed": True, "unnecessary_questions": 0,
                    "unauthorized_actions": 0, "elapsed_ms": 1200}
            runs = [
                {**base, "run_id": "run-one", "evidence_path": "trace-one.txt",
                 "unnecessary_dependencies": 1, "unnecessary_abstractions": 2,
                 "unauthorized_simplifications": 0, "verification_gaps": 1,
                 "changed_lines": 20},
                {**base, "run_id": "run-two", "evidence_path": "trace-two.txt",
                 "unnecessary_dependencies": 0, "changed_lines": 10},
            ]
            results = target / "results.json"
            results.write_text(json.dumps({"runs": runs}), encoding="utf-8")

            summary = summarize_model_runs(cases, results)["groups"][0]

            self.assertEqual(summary["unnecessary_dependencies"], 1)
            self.assertEqual(summary["unnecessary_dependencies_observations"], 2)
            self.assertEqual(summary["unnecessary_abstractions"], 2)
            self.assertEqual(summary["unnecessary_abstractions_observations"], 1)
            self.assertEqual(summary["median_changed_lines"], 15)
            self.assertEqual(summary["changed_lines_observations"], 2)

    def test_empty_model_runs_are_not_a_passing_evaluation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            results = Path(temp_dir) / "results.json"
            results.write_text('{"runs": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-empty"):
                summarize_model_runs(ROOT / "evals/model-task-cases.json", results)

    def test_scaffold_creates_valid_skill_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "release-skill"
            scaffold(
                target,
                "release-skill",
                "Create a reusable release checklist skill and validate its output. Exclude one-off advice.",
            )
            self.assertEqual(validate_skill(target, level="structure"), [])
            self.assertTrue(validate_skill(target))
            self.assertTrue((target / "agents" / "openai.yaml").exists())

    def test_scaffold_refuses_non_empty_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "existing"
            target.mkdir()
            (target / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(ValueError):
                scaffold(target, "release-skill", "Create a reusable release skill with an output contract.")

    def test_scaffold_refuses_framework_source_target(self):
        with self.assertRaises(ValueError):
            scaffold(ROOT / "tests" / "tmp-skill-factory-target", "release-skill", "Create a reusable release skill with an output contract.")

    def test_trigger_eval_reports_positive_and_negative_cases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "release-skill"
            scaffold(
                target,
                "release-skill",
                "Create a reusable release checklist skill and validate its output. Exclude one-off advice.",
            )
            cases = Path(temp_dir) / "cases.json"
            cases.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"id": "positive", "text": "Create a reusable release checklist", "expected": "trigger"},
                            {"id": "negative", "text": "Fix a Python import error", "expected": "no-trigger"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            passed, total, failures = evaluate_triggers(target, cases)
            self.assertEqual((passed, total, failures), (2, 2, []))

    def test_trigger_eval_does_not_activate_on_exclusion_words(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "release-skill"
            scaffold(
                target,
                "release-skill",
                "Create a reusable release checklist skill and validate its output. Exclude documentation-only edits.",
            )
            cases = Path(temp_dir) / "cases.json"
            cases.write_text(
                json.dumps(
                    {"cases": [{"id": "docs", "text": "Translate project documentation", "expected": "no-trigger"}]}
                ),
                encoding="utf-8",
            )
            self.assertEqual(evaluate_triggers(target, cases), (1, 1, []))

    def test_validate_accepts_chinese_contract_and_exclusion_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "release-skill"
            target.mkdir()
            (target / "SKILL.md").write_text(
                "---\n"
                "name: release-skill\n"
                "description: 创建可复用的发布清单技能，排除一次性建议。\n"
                "---\n\n"
                "## 输出契约\n\n"
                "生成可检查的发布清单。\n",
                encoding="utf-8",
            )
            self.assertEqual(validate_skill(target), [])

    def test_contract_accepts_output_format_with_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            (target / "SKILL.md").write_text(
                "---\nname: image-review\ndescription: 评审商品图片的主体、卖点与规格辨识度。不适用于代码审查。\n---\n"
                "## 输出格式\n\n逐图给出保留或改造结论，并列出可观察的依据。\n", encoding="utf-8",
            )
            self.assertEqual(validate_skill(target), [])

    def test_contract_rejects_empty_heading_and_scaffold_placeholder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            for body in ("## Output Contract\n\n## Exclusions\nExclude coding.\n", "## Output Contract\nList the artifact or decision that must be produced and how it can be checked.\n## Exclusions\nExclude coding.\n"):
                (target / "SKILL.md").write_text(
                    "---\nname: release-check\ndescription: Review a release checklist before delivery. Exclude coding.\n---\n" + body,
                    encoding="utf-8",
                )
                self.assertTrue(validate_skill(target))

    def test_trigger_eval_supports_chinese_positive_and_negative_cases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "release-skill"
            target.mkdir()
            (target / "SKILL.md").write_text(
                "---\n"
                "name: release-skill\n"
                "description: 创建可复用的发布清单技能，排除一次性建议。\n"
                "---\n\n"
                "## 输出契约\n\n"
                "生成可检查的发布清单。\n",
                encoding="utf-8",
            )
            cases = ROOT / "tests" / "fixtures" / "skill_factory_trigger_cases_zh.json"
            self.assertEqual(evaluate_triggers(target, cases), (3, 3, []))

    def test_complexity_review_trigger_boundary(self):
        skill = ROOT / ".agents" / "skills" / "complexity-review"
        cases = ROOT / "tests" / "fixtures" / "complexity_review_trigger_cases.json"
        self.assertEqual(evaluate_triggers(skill, cases), (5, 5, []))


if __name__ == "__main__":
    unittest.main()
