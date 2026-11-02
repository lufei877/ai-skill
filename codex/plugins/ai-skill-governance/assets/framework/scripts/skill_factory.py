#!/usr/bin/env python3
"""Create and validate small, portable Codex skill packages."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import median
from typing import Any

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
ENGINE_ROOT = Path(__file__).resolve().parent.parent
STOPWORDS = {
    "a", "an", "and", "are", "for", "from", "has", "into", "its", "of",
    "on", "or", "the", "this", "to", "use", "when", "with", "your",
}
EXCLUSION_MARKERS = ("exclude", "排除", "不适用")
CONTRACT_MARKERS = ("output contract", "输出契约", "输出合同", "输出格式", "输出要求")
PLACEHOLDERS = (
    "List the artifact or decision that must be produced and how it can be checked.",
    "Describe the recurring job this skill owns.",
    "State nearby requests that should not trigger this skill.",
)
CHINESE_STOPWORDS = {
    "一个", "一种", "这个", "这是", "以及", "用于", "进行", "相关", "内容", "请求",
}


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    return parse_skill_text(path.read_text(encoding="utf-8"))


def parse_skill_text(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}, text
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, text[match.end():]


def meaningful_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    english = {word for word in words if len(word) > 2 and word not in STOPWORDS}
    chinese: set[str] = set()
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        for size in (2, 3):
            chinese.update(run[index:index + size] for index in range(len(run) - size + 1))
    chinese.difference_update(CHINESE_STOPWORDS)
    return english | chinese


def contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def before_exclusion(text: str) -> str:
    lowered = text.lower()
    positions = [lowered.find(marker) for marker in EXCLUSION_MARKERS]
    positions = [position for position in positions if position >= 0]
    return text[:min(positions)] if positions else text


def validate_skill(skill_dir: Path, *, level: str = "contract") -> list[str]:
    skill_file = skill_dir / "SKILL.md"
    if not skill_dir.is_dir():
        return [f"target is not a directory: {skill_dir}"]
    if not skill_file.is_file():
        return ["missing SKILL.md"]
    return validate_skill_text(skill_file.read_text(encoding="utf-8"), level=level)


def validate_skill_text(text: str, *, level: str = "contract") -> list[str]:
    """Check syntax and explicit contract content, not semantic task quality."""
    if level not in {"structure", "contract"}:
        raise ValueError(f"Unknown validation level: {level}")
    errors: list[str] = []
    metadata, body = parse_skill_text(text)
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not name or not NAME_PATTERN.fullmatch(name) or len(name) > 64:
        errors.append("name must use lowercase kebab-case and be at most 64 characters")
    if not description or len(description) > 1024:
        errors.append("description must be non-empty and at most 1024 characters")
    if not body.strip():
        errors.append("SKILL.md body must not be empty")
    if level == "contract":
        sections = re.findall(r"^#{1,6} +([^\n]+)\n(.*?)(?=^#{1,6} |\Z)", body, re.MULTILINE | re.DOTALL)
        if not any(contains_marker(title, CONTRACT_MARKERS) and content.strip() for title, content in sections):
            errors.append("body must state a non-empty output contract section")
        if not contains_marker(description, EXCLUSION_MARKERS) and not contains_marker(body, EXCLUSION_MARKERS):
            errors.append("description or body must state an exclusion boundary")
        if any(placeholder in body for placeholder in PLACEHOLDERS):
            errors.append("replace scaffold placeholders before contract validation")
    return errors


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError("trigger cases must be an object containing a cases array")
    if not cases or not all(isinstance(case, dict) for case in cases):
        raise ValueError("trigger cases must contain non-empty case objects")
    return cases


def evaluate_triggers(skill_dir: Path, cases_path: Path) -> tuple[int, int, list[str]]:
    metadata, _ = parse_frontmatter(skill_dir / "SKILL.md")
    # Exclusion wording is a boundary, not positive evidence for activation.
    description = metadata.get("description", "")
    description_words = meaningful_words(before_exclusion(description))
    cases = load_cases(cases_path)
    passed = 0
    failures: list[str] = []
    for case in cases:
        case_id = str(case.get("id", "unnamed"))
        text = str(case.get("text", ""))
        expected = case.get("expected")
        overlap = meaningful_words(text) & description_words
        actual = "trigger" if len(overlap) >= 2 else "no-trigger"
        if expected not in {"trigger", "no-trigger"}:
            failures.append(f"{case_id}: expected must be trigger or no-trigger")
        elif actual == expected:
            passed += 1
        else:
            failures.append(f"{case_id}: expected {expected}, got {actual}")
    return passed, len(cases), failures


def summarize_model_runs(cases_path: Path, results_path: Path) -> dict[str, object]:
    """Summarize supplied observations; never synthesize or run model evidence."""
    suite = json.loads(cases_path.read_text(encoding="utf-8"))
    case_list = load_cases(cases_path)
    variants = suite.get("variants")
    if not isinstance(variants, list) or not variants or not all(isinstance(variant, str) for variant in variants):
        raise ValueError("model cases require a non-empty variants list")
    for case in case_list:
        if not isinstance(case.get("id"), str) or not case["id"]:
            raise ValueError("model cases require non-empty IDs")
        for field in ("required_skills", "forbidden_skills"):
            if not isinstance(case.get(field), list) or not all(isinstance(name, str) for name in case[field]):
                raise ValueError(f"model case requires {field} names")
    cases = {case["id"]: case for case in case_list}
    if len(cases) != len(case_list):
        raise ValueError("duplicate model case ID")
    results = json.loads(results_path.read_text(encoding="utf-8"))
    runs = results.get("runs") if isinstance(results, dict) else None
    if not isinstance(runs, list) or not runs:
        raise ValueError("model evaluation requires actual non-empty run records")
    groups: dict[tuple[str, str, str], list[dict]] = {}
    seen: set[str] = set()
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("each run must be an object")
        for field in ("case_id", "variant", "model", "reasoning", "run_id", "evidence_path"):
            if not isinstance(run.get(field), str) or not run[field].strip():
                raise ValueError(f"run requires non-empty {field}")
        if run["run_id"] in seen:
            raise ValueError(f"duplicate run_id: {run['run_id']}")
        seen.add(run["run_id"])
        if run["case_id"] not in cases or run["variant"] not in suite["variants"]:
            raise ValueError("unknown case or variant")
        evidence = results_path.parent / run["evidence_path"]
        if not evidence.is_file() or not evidence.stat().st_size:
            raise ValueError(f"missing or empty run evidence: {evidence}")
        skills = run.get("selected_skills")
        if not isinstance(skills, list) or not all(isinstance(skill, str) for skill in skills):
            raise ValueError("selected_skills must be a list of names")
        if type(run.get("outcome_passed")) is not bool:
            raise ValueError("outcome_passed must be an observed boolean")
        for field in ("unnecessary_questions", "unauthorized_actions", "elapsed_ms"):
            if type(run.get(field)) is not int or run[field] < 0:
                raise ValueError(f"{field} must be a nonnegative integer")
        for field in (
            "input_tokens", "unnecessary_dependencies", "unnecessary_abstractions",
            "unauthorized_simplifications", "verification_gaps", "changed_lines",
        ):
            if field in run and (type(run[field]) is not int or run[field] < 0):
                raise ValueError(f"{field} must be a nonnegative observed integer")
        groups.setdefault((run["model"], run["reasoning"], run["variant"]), []).append(run)
    summaries = []
    for (model, reasoning, variant), observations in sorted(groups.items()):
        routing_passed = None if variant == "without-library" else sum(
            set(cases[run["case_id"]]["required_skills"]).issubset(run["selected_skills"])
            and not set(cases[run["case_id"]]["forbidden_skills"]).intersection(run["selected_skills"])
            for run in observations
        )
        tokens = [run["input_tokens"] for run in observations if "input_tokens" in run]
        optional_counts = {
            field: [run[field] for run in observations if field in run]
            for field in (
                "unnecessary_dependencies", "unnecessary_abstractions",
                "unauthorized_simplifications", "verification_gaps",
            )
        }
        changed_lines = [run["changed_lines"] for run in observations if "changed_lines" in run]
        summaries.append({
            "model": model, "reasoning": reasoning, "variant": variant, "runs": len(observations),
            "outcome_passed": sum(run["outcome_passed"] for run in observations),
            "routing_passed": routing_passed,
            "missing_cases": sorted(set(cases) - {run["case_id"] for run in observations}),
            "unnecessary_questions": sum(run["unnecessary_questions"] for run in observations),
            "unauthorized_actions": sum(run["unauthorized_actions"] for run in observations),
            "median_elapsed_ms": median(run["elapsed_ms"] for run in observations),
            "median_input_tokens": median(tokens) if tokens else None,
            "token_observations": len(tokens),
            **{
                field: sum(values) if values else None
                for field, values in optional_counts.items()
            },
            **{
                f"{field}_observations": len(values)
                for field, values in optional_counts.items()
            },
            "median_changed_lines": median(changed_lines) if changed_lines else None,
            "changed_lines_observations": len(changed_lines),
        })
    missing_variants = [
        {"model": model, "reasoning": reasoning, "variant": variant}
        for model, reasoning in sorted({(key[0], key[1]) for key in groups})
        for variant in variants if (model, reasoning, variant) not in groups
    ]
    return {
        "evidence": "supplied observations; scores require independent review",
        "groups": summaries, "missing_variants": missing_variants,
    }


def scaffold(target: Path, name: str, description: str) -> None:
    target = target.resolve()
    try:
        target.relative_to(ENGINE_ROOT)
    except ValueError:
        pass
    else:
        raise ValueError(f"refusing target inside ai-skill source: {target}")
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"refusing non-empty target: {target}")
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        "metadata:\n"
        "  short-description: Reusable skill\n"
        "---\n\n"
        f"# {name}\n\n"
        "## Purpose\n\n"
        "Describe the recurring job this skill owns.\n\n"
        "## Rules\n\n"
        "1. State the smallest workflow that produces the intended result.\n"
        "2. Keep project-specific facts in project knowledge, not this shared skill.\n\n"
        "## Output Contract\n\n"
        "List the artifact or decision that must be produced and how it can be checked.\n\n"
        "## Exclusions\n\n"
        "State nearby requests that should not trigger this skill.\n",
        encoding="utf-8",
    )
    (target / "agents").mkdir()
    (target / "agents" / "openai.yaml").write_text(
        "interface:\n"
        f"  display_name: \"{name}\"\n"
        "  short_description: \"Reusable skill\"\n"
        f"  default_prompt: \"Use ${name} for this recurring workflow.\"\n\n"
        "policy:\n"
        "  allow_implicit_invocation: true\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and validate reusable Codex skills")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scaffold_parser = subparsers.add_parser("scaffold", help="create a new skill in an empty target")
    scaffold_parser.add_argument("target", type=Path)
    scaffold_parser.add_argument("--name", required=True)
    scaffold_parser.add_argument("--description", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate an existing skill")
    validate_parser.add_argument("skill_dir", type=Path)
    validate_parser.add_argument("--level", choices=("structure", "contract"), default="contract")

    library_parser = subparsers.add_parser("validate-library", help="validate all central skill contracts")
    library_parser.add_argument("root", type=Path, nargs="?", default=ENGINE_ROOT)

    model_parser = subparsers.add_parser("model-eval", help="summarize supplied real model run evidence")
    model_parser.add_argument("--cases", type=Path, required=True)
    model_parser.add_argument("--results", type=Path, required=True)

    eval_parser = subparsers.add_parser("trigger-eval", help="run deterministic trigger smoke cases")
    eval_parser.add_argument("skill_dir", type=Path)
    eval_parser.add_argument("--cases", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == "scaffold":
            if not NAME_PATTERN.fullmatch(args.name) or len(args.name) > 64:
                raise ValueError("name must use lowercase kebab-case and be at most 64 characters")
            scaffold(args.target.resolve(), args.name, args.description)
            print(f"[OK] scaffolded {args.target.resolve()}")
            return 0
        if args.command == "validate-library":
            from codex_support import native_skill_payloads

            payloads = native_skill_payloads(args.root.resolve())
            skills = {path: text for path, text in payloads.items() if path.name == "SKILL.md"}
            if not skills:
                raise ValueError(f"No central skills found: {args.root}")
            failures = [(path, error) for path, text in skills.items() for error in validate_skill_text(text)]
            for path, error in failures:
                print(f"[FAIL] {path}: {error}")
            print(f"[CONTRACT] {len(skills)} central skills; {len(failures)} errors; model behavior not evaluated")
            return 1 if failures else 0
        if args.command == "model-eval":
            print(json.dumps(summarize_model_runs(args.cases, args.results), ensure_ascii=False, indent=2))
            return 0
        if args.command == "validate":
            errors = validate_skill(args.skill_dir.resolve(), level=args.level)
            if errors:
                for error in errors:
                    print(f"[FAIL] {error}")
                return 1
            print(f"[OK] valid skill: {args.skill_dir.resolve()}")
            return 0
        errors = validate_skill(args.skill_dir.resolve())
        if errors:
            for error in errors:
                print(f"[FAIL] {error}")
            return 1
        passed, total, failures = evaluate_triggers(args.skill_dir.resolve(), args.cases.resolve())
        print(f"[LEXICAL SMOKE] {passed}/{total} cases passed; not a model evaluation")
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 0 if not failures else 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
