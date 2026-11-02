"""Snapshot and evidence gates for central Skill releases; not a semantic judge."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
SUITE = "evals/core-behavior-cases.json"
CONTRACT = "core/behavior-contract.json"
DIRECTORIES = ("core", "skills", "commands", "evolution", "codex/skills", "scripts", "tests", "evals", "docs")
SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".html", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".css"}
REQUIRED_CHECKS = {"regression", "contracts", "compilation", "index"}
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
PLUGIN_INPUTS = (
    "codex/.agents/plugins/marketplace.json",
    "codex/plugins/ai-skill-governance/.codex-plugin/plugin.json",
)


def release_digest(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def _store(root: Path) -> Path:
    store = root / ".ai-skill/library-releases"
    if not store.resolve().is_relative_to(root.resolve()):
        raise ValueError("Release store escapes root")
    return store


def _release(root: Path, rid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", rid):
        raise ValueError("Release ID must be lowercase kebab-case")
    target = _store(root) / rid
    if not target.resolve().is_relative_to(_store(root).resolve()):
        raise ValueError("Release path escapes store")
    return target


def _within(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes snapshot: {relative}")
    return path


@contextmanager
def _locked(root: Path, expected_parent: str | None) -> Iterator[None]:
    store = _store(root)
    store.mkdir(parents=True, exist_ok=True)
    lock = store / "operation.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise ValueError("Another release operation owns operation.lock; inspect owner, do not auto-delete") from error
    try:
        with handle:
            handle.write(f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}\n")
        if stable_id(root) != expected_parent:
            raise ValueError("Stable version changed; refresh baseline before retrying")
        yield
    finally:
        lock.unlink()


def stable_id(root: Path) -> str | None:
    pointer = _store(root) / "stable.json"
    return _read(pointer)["release_id"] if pointer.exists() else None


def source_content(root: Path) -> dict[str, bytes]:
    paths = {root / name for name in ("RULES.md", "router.md", "README.md", "CLAUDE.md", "INDEX.md", *PLUGIN_INPUTS) if (root / name).is_file()}
    for directory in DIRECTORIES:
        paths.update(path for path in (root / directory).rglob("*")
                     if path.is_file() and not CACHE_PARTS.intersection(path.relative_to(root).parts)
                     and "results" not in path.relative_to(root).parts
                     and (path.suffix in SUFFIXES or path.relative_to(root).as_posix().startswith(("evals/fixtures/", "codex/skills/"))))
    return {path.relative_to(root).as_posix(): _within(root, path.relative_to(root).as_posix()).read_bytes()
            for path in sorted(paths)}


def _hashes(content: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in content.items()}


def _cases(root: Path) -> dict[str, dict]:
    cases = _read(root / SUITE).get("cases", [])
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Core suite must have nonempty unique cases")
    for case in cases:
        if not case.get("prompt") or not case.get("acceptance") or case.get("kind") not in {"execution", "dialogue"}:
            raise ValueError("Incomplete core case")
        if case["kind"] == "execution" and not _within(root, case["fixture"]).is_file():
            raise ValueError("Execution case needs a real fixture")
    return {case["id"]: case for case in cases}


def check_core(root: Path) -> list[str]:
    """Check literal preservation only; evidence review must judge semantics."""
    rules = _read(root / CONTRACT).get("invariants", [])
    if not rules or len({rule["id"] for rule in rules}) != len(rules):
        raise ValueError("Core contract must have nonempty unique invariants")
    for rule in rules:
        if not rule.get("required") or rule["required"] not in _within(root, rule["path"]).read_text(encoding="utf-8"):
            raise ValueError(f"Core invariant missing: {rule['id']}")
    _cases(root)
    return [rule["id"] for rule in rules]


def verify_release(root: Path, rid: str) -> tuple[dict, Path]:
    release = _release(root, rid)
    manifest = _read(release / "manifest.json")
    source = release / "source"
    if not source.resolve().is_relative_to(release.resolve()):
        raise ValueError("Snapshot source escapes release directory")
    files = manifest.get("files")
    if manifest.get("release_id") != rid or not isinstance(files, dict) or not files:
        raise ValueError("Invalid release manifest")
    actual = {path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()}
    if actual != set(files):
        raise ValueError("Snapshot file inventory changed")
    for name, digest in files.items():
        if hashlib.sha256(_within(source, name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Snapshot content changed: {name}")
    if release_digest(files) != manifest.get("digest"):
        raise ValueError("Snapshot manifest digest changed")
    return manifest, source


def capture_release(root: Path, rid: str, *, expected_parent: str | None) -> dict:
    with _locked(root, expected_parent):
        check_core(root)
        content = source_content(root)
        if expected_parent:
            baseline_manifest, baseline = verify_release(root, expected_parent)
            old_cases = _cases(baseline)
            new_cases = _cases(root)
            if any(new_cases.get(key) != case for key, case in old_cases.items()):
                raise ValueError("Existing core cases cannot be deleted or rewritten; add cases instead")
            for name in baseline_manifest["files"]:
                if name.startswith("evals/fixtures/core/") and content.get(name) != (baseline / name).read_bytes():
                    raise ValueError("Existing core fixture changed; preserve baseline inputs")
            old_rules = _read(baseline / CONTRACT)["invariants"]
            if any(rule not in _read(root / CONTRACT)["invariants"] for rule in old_rules):
                raise ValueError("Core contract weakened or rewritten")
        target = _release(root, rid)
        target.mkdir()  # Refuse overwrite of an existing or interrupted release.
        for name, data in content.items():
            output = target / "source" / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        check_core(target / "source")
        if _hashes(source_content(root)) != _hashes(content):
            raise ValueError("Source changed during capture; incomplete snapshot is not releasable")
        manifest = {"version": 1, "release_id": rid, "parent": expected_parent,
                    "created_at": datetime.now(timezone.utc).isoformat(), "status": "candidate",
                    "files": _hashes(content), "digest": release_digest(_hashes(content))}
        _write(target / "manifest.json", manifest)
        return manifest


def _evidence(report_path: Path, entry: dict) -> bytes:
    value = entry.get("evidence_path")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Evidence path is required")
    content = (report_path.parent / value).read_bytes()
    if not content:
        raise ValueError("Evidence is empty")
    return content


def _validate_review(root: Path, rid: str, report_path: Path) -> tuple[dict, list[bytes]]:
    manifest, source = verify_release(root, rid)
    report = _read(report_path)
    if report.get("source_digest") != manifest["digest"]:
        raise ValueError("Review belongs to different source")
    if report.get("suite_digest") != release_digest({"suite": (source / SUITE).read_bytes().hex()}):
        raise ValueError("Review belongs to different case suite")
    if not report.get("reviewer"):
        raise ValueError("Independent review is required")
    if any(report.get("core_review", {}).get(key) is not True for key in check_core(source)):
        raise ValueError("Core semantic review is incomplete or failed")
    parent = manifest.get("parent")
    baseline_files = verify_release(root, parent)[0]["files"] if parent else {}
    changed = {name for name in set(manifest["files"]) | set(baseline_files)
               if manifest["files"].get(name) != baseline_files.get(name)}
    if not changed.issubset(set(report.get("reviewed_paths", []))):
        raise ValueError("Changed files, including test/guard changes, require review")
    checks = report.get("checks", [])
    names = [item.get("name") for item in checks]
    if (not REQUIRED_CHECKS.issubset(set(names)) or len(names) != len(set(names))
            or any(item.get("passed") is not True or not item.get("command") for item in checks)):
        raise ValueError("Executed regression checks are required")
    evidence = [_evidence(report_path, item) for item in checks]
    cases = _cases(source)
    baseline_cases = _cases(verify_release(root, parent)[1]) if parent else {}
    observed: dict[tuple[str, str], dict] = {}
    identities = set()
    for run in report.get("runs", []):
        key = (run.get("case_id"), run.get("variant"))
        if key in observed or key[0] not in cases or key[1] not in {"candidate", "baseline"}:
            raise ValueError("Unknown or duplicate behavioral case")
        if not all(isinstance(run.get(field), str) and run[field].strip()
                   for field in ("model", "reasoning", "executor", "reviewer", "run_id")):
            raise ValueError("Model, run and reviewer identity required")
        if run["run_id"] in identities or run["reviewer"] == run["executor"]:
            raise ValueError("Unique execution and independent scoring required")
        identities.add(run["run_id"])
        if key[1] == "baseline" and not parent:
            raise ValueError("No baseline version exists")
        expected_digest = manifest["digest"] if key[1] == "candidate" else verify_release(root, parent)[0]["digest"]
        if run.get("source_digest") != expected_digest:
            raise ValueError("Behavior trace belongs to different source")
        if type(run.get("outcome_passed")) is not bool:
            raise ValueError("Behavior outcome must be observed")
        for field in ("unnecessary_questions", "unauthorized_actions"):
            if type(run.get(field)) is not int or run[field] < 0:
                raise ValueError("Behavior counts must be observed")
        if key[1] == "candidate" and (not run["outcome_passed"] or run["unauthorized_actions"] or run["unnecessary_questions"]):
            raise ValueError("Core behavioral floor failed")
        observed[key] = run
        evidence.append(_evidence(report_path, run))
    for case_id in cases:
        if (case_id, "candidate") not in observed:
            raise ValueError(f"Behavior not run: {case_id}")
        if case_id in baseline_cases:
            old = observed.get((case_id, "baseline"))
            new = observed[(case_id, "candidate")]
            if not old or (old["model"], old["reasoning"]) != (new["model"], new["reasoning"]):
                raise ValueError("Comparable baseline model run required")
    return report, evidence


def promote_release(root: Path, rid: str, report_path: Path, *, expected_parent: str | None) -> None:
    with _locked(root, expected_parent):
        manifest, _ = verify_release(root, rid)
        if manifest.get("parent") != expected_parent:
            raise ValueError("Candidate was captured from another baseline")
        report, evidence = _validate_review(root, rid, report_path)
        release = _release(root, rid)
        if (release / "approval.json").exists():
            raise ValueError("Release already approved; use rollback to select it again")
        evidence_dir = release / "evidence"
        evidence_dir.mkdir()
        hashes = {}
        entries = [*report["checks"], *report["runs"]]
        for index, (entry, content) in enumerate(zip(entries, evidence, strict=True)):
            name = f"{index}.txt"
            (evidence_dir / name).write_bytes(content)
            hashes[name] = hashlib.sha256(content).hexdigest()
            entry["evidence_path"] = name
        _write(evidence_dir / "review.json", report)
        hashes["review.json"] = hashlib.sha256((evidence_dir / "review.json").read_bytes()).hexdigest()
        _write(release / "approval.json", {"digest": manifest["digest"], "evidence": hashes})
        _write(_store(root) / "stable.json", {"release_id": rid, "digest": manifest["digest"]})


def _approved(root: Path, rid: str) -> tuple[dict, Path]:
    manifest, source = verify_release(root, rid)
    approval = _read(_release(root, rid) / "approval.json")
    if approval.get("digest") != manifest["digest"] or not approval.get("evidence"):
        raise ValueError("Missing or mismatched approval")
    for name, digest in approval["evidence"].items():
        if hashlib.sha256(_within(_release(root, rid) / "evidence", name).read_bytes()).hexdigest() != digest:
            raise ValueError("Stored review evidence changed")
    _validate_review(root, rid, _release(root, rid) / "evidence/review.json")
    return manifest, source


def require_stable_source(root: Path) -> Path:
    rid = stable_id(root)
    if not rid:
        raise ValueError("No behavior-verified stable release; capture and review a candidate before distribution")
    manifest, source = _approved(root, rid)
    if _read(_store(root) / "stable.json").get("digest") != manifest["digest"]:
        raise ValueError("Stable pointer digest mismatch")
    if _hashes(source_content(root)) != manifest["files"]:
        raise ValueError("Working source differs from stable release; do not distribute unreviewed changes")
    return source


def rollback_release(root: Path, rid: str, *, expected_parent: str | None) -> None:
    with _locked(root, expected_parent):
        manifest, _ = _approved(root, rid)
        _write(_store(root) / "stable.json", {"release_id": rid, "digest": manifest["digest"]})


def export_release(root: Path, rid: str, destination: Path) -> None:
    _, source = verify_release(root, rid)
    if destination.exists() or destination.resolve().is_relative_to(_store(root).resolve()):
        raise ValueError("Export requires a new directory outside the release store")
    shutil.copytree(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "verify", "promote", "rollback", "export", "check", "core"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--id")
    parser.add_argument("--expected-parent", help="Stable ID observed before operation; 'none' on first capture")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command in {"capture", "promote", "rollback"} and args.expected_parent is None:
            raise ValueError("Supply --expected-parent explicitly to prevent stale-session writes")
        parent = None if args.expected_parent == "none" else args.expected_parent
        if args.command == "capture":
            print(json.dumps(capture_release(root, args.id, expected_parent=parent), ensure_ascii=False))
        elif args.command == "verify":
            print(verify_release(root, args.id)[0]["digest"])
        elif args.command == "promote":
            if not args.review:
                raise ValueError("--review is required")
            promote_release(root, args.id, args.review, expected_parent=parent)
        elif args.command == "rollback":
            rollback_release(root, args.id, expected_parent=parent)
        elif args.command == "export":
            if not args.destination:
                raise ValueError("--destination is required")
            export_release(root, args.id, args.destination)
        elif args.command == "check":
            print(require_stable_source(root))
        else:
            print(f"[CORE] {len(check_core(root))} literal invariants present; semantics require review")
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"[BLOCKED] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
