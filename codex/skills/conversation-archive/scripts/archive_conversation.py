#!/usr/bin/env python3
"""Configure and write redacted project conversation summaries."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

POLICY_RELATIVE = Path(".ai-skill/project/conversation-archive.json")
DEFAULT_OUTPUT_DIRECTORY = ".ai-skill/project/conversations"
ALLOWED_CADENCES = {"off", "manual", "daily", "weekly"}
LIST_FIELDS = (
    "goals",
    "confirmed_facts",
    "decisions",
    "changed_files",
    "unresolved_items",
    "next_steps",
    "user_preferences",
)
ALLOWED_SUMMARY_FIELDS = {"session_id", "date", "transcript_path", *LIST_FIELDS}
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
DAILY_FILE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
SECRET_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (
        re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{12,}"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(password|passwd|token|secret|api[_ -]?key|cookie)\s*[:=]\s*\S+"
        ),
        r"\1=[REDACTED]",
    ),
)
MAX_LIST_ITEMS = 50
MAX_ITEM_LENGTH = 2_000
MAX_TRANSCRIPT_PATH_LENGTH = 2_048


@dataclass(frozen=True)
class ArchivePolicy:
    """Validated project-local archive policy."""

    cadence: str
    output_directory: str
    retention_days: int | None
    exists: bool


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _project_root(raw_project: str) -> Path:
    project = Path(raw_project).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"Project directory does not exist: {project}")
    return project


def _output_path(project: Path, relative: str) -> Path:
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError("output_directory must be relative to the project")
    resolved = (project / raw).resolve()
    try:
        resolved.relative_to(project)
    except ValueError as error:
        raise ValueError("output_directory must stay inside the project") from error
    return resolved


def load_policy(project: Path) -> ArchivePolicy:
    """Load policy; a missing policy is intentionally disabled."""
    path = project / POLICY_RELATIVE
    if not path.exists():
        return ArchivePolicy("off", DEFAULT_OUTPUT_DIRECTORY, None, False)

    payload = _read_json(path, {})
    if payload.get("version") != 1:
        raise ValueError(f"Unsupported conversation archive policy: {path}")
    cadence = payload.get("cadence")
    if cadence not in ALLOWED_CADENCES:
        raise ValueError(f"Invalid cadence in {path}: {cadence}")
    output_directory = payload.get("output_directory", DEFAULT_OUTPUT_DIRECTORY)
    if not isinstance(output_directory, str) or not output_directory.strip():
        raise ValueError(f"Invalid output_directory in {path}")
    _output_path(project, output_directory)

    retention_days = payload.get("retention_days")
    if retention_days is not None and (
        not isinstance(retention_days, int)
        or isinstance(retention_days, bool)
        or retention_days < 1
    ):
        raise ValueError(f"retention_days must be null or a positive integer in {path}")
    return ArchivePolicy(cadence, output_directory, retention_days, True)


def configure_project(args: argparse.Namespace) -> dict:
    project = _project_root(args.project)
    existing = load_policy(project)
    output_directory = args.output_directory or existing.output_directory
    _output_path(project, output_directory)
    if args.retention_days is not None and args.retention_days < 0:
        raise ValueError("retention_days must be zero or a positive integer")
    retention_days = existing.retention_days
    if args.retention_days is not None:
        retention_days = args.retention_days or None
    payload = {
        "version": 1,
        "cadence": args.cadence,
        "output_directory": output_directory,
        "retention_days": retention_days,
    }
    policy_path = project / POLICY_RELATIVE
    _write_text(policy_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return {"configured": True, "project": str(project), "policy": str(policy_path), **payload}


def _parse_day(raw: str | None) -> date:
    if raw is None:
        return datetime.now().astimezone().date()
    if not isinstance(raw, str):
        raise ValueError(f"Invalid date, expected YYYY-MM-DD: {raw}")
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise ValueError(f"Invalid date, expected YYYY-MM-DD: {raw}") from error


def _load_index(output: Path) -> dict:
    payload = _read_json(output / "index.json", {"version": 1, "sessions": []})
    sessions = payload.get("sessions")
    if (
        payload.get("version") != 1
        or not isinstance(sessions, list)
        or not all(isinstance(entry, dict) for entry in sessions)
    ):
        raise ValueError(f"Invalid conversation index: {output / 'index.json'}")
    return payload


def archive_due(args: argparse.Namespace) -> dict:
    project = _project_root(args.project)
    policy = load_policy(project)
    current_day = _parse_day(args.date)
    if not policy.exists:
        return {"due": False, "cadence": "off", "reason": "policy-missing"}
    if policy.cadence == "off":
        return {"due": False, "cadence": "off", "reason": "disabled"}
    if policy.cadence == "manual":
        return {"due": False, "cadence": "manual", "reason": "manual-only"}

    output = _output_path(project, policy.output_directory)
    sessions = _load_index(output)["sessions"] if output.exists() else []
    archived_days: list[date] = []
    for entry in sessions:
        if not isinstance(entry, dict) or not isinstance(entry.get("date"), str):
            continue
        try:
            archived_days.append(date.fromisoformat(entry["date"]))
        except ValueError:
            continue

    if policy.cadence == "daily":
        due = current_day not in archived_days
        period = current_day.isoformat()
    else:
        iso_year, iso_week, _ = current_day.isocalendar()
        due = not any(day.isocalendar()[:2] == (iso_year, iso_week) for day in archived_days)
        period = f"{iso_year}-W{iso_week:02d}"
    return {
        "due": due,
        "cadence": policy.cadence,
        "period": period,
        "reason": "not-archived" if due else "already-archived",
    }


def _clean_text(value: str) -> str:
    cleaned = " ".join(value.splitlines()).strip()
    for pattern, replacement in SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned.replace("<!--", "&lt;!--").replace("-->", "--&gt;")


def _validate_summary(payload: dict) -> dict:
    unknown = sorted(set(payload) - ALLOWED_SUMMARY_FIELDS)
    if unknown:
        raise ValueError(f"Unsupported summary fields: {', '.join(unknown)}")
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError("session_id must contain only letters, digits, '.', '_', ':', or '-'")

    normalized: dict[str, object] = {"session_id": session_id}
    archive_day = _parse_day(payload.get("date"))
    normalized["date"] = archive_day.isoformat()
    transcript_path = payload.get("transcript_path")
    if transcript_path is not None and not isinstance(transcript_path, str):
        raise ValueError("transcript_path must be a string or null")
    if transcript_path and len(transcript_path) > MAX_TRANSCRIPT_PATH_LENGTH:
        raise ValueError("transcript_path is too long")
    normalized["transcript_path"] = _clean_text(transcript_path) if transcript_path else None

    for field in LIST_FIELDS:
        values = payload.get(field, [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError(f"{field} must be a list of strings")
        if len(values) > MAX_LIST_ITEMS:
            raise ValueError(f"{field} cannot contain more than {MAX_LIST_ITEMS} items")
        if any(len(item) > MAX_ITEM_LENGTH for item in values):
            raise ValueError(f"{field} items cannot exceed {MAX_ITEM_LENGTH} characters")
        cleaned_values = [_clean_text(item) for item in values]
        normalized[field] = [item for item in cleaned_values if item]
    if not normalized["goals"]:
        raise ValueError("goals must contain at least one item")
    return normalized


def _list_section(title: str, values: list[str]) -> list[str]:
    items = [f"- {value}" for value in values] or ["- 无"]
    return [f"### {title}", "", *items, ""]


def _render_session(summary: dict) -> str:
    session_id = summary["session_id"]
    transcript_path = str(summary["transcript_path"] or "未提供").replace("`", "'")
    lines = [
        f"<!-- conversation:{session_id}:start -->",
        f"## 会话 `{session_id}`",
        "",
        f"- 日期: `{summary['date']}`",
        f"- 原始记录: `{transcript_path}`",
        "",
    ]
    sections = (
        ("讨论主题与用户目标", "goals"),
        ("已确认事实", "confirmed_facts"),
        ("已确认决策", "decisions"),
        ("修改文件", "changed_files"),
        ("未完成事项", "unresolved_items"),
        ("下一步", "next_steps"),
        ("用户明确偏好", "user_preferences"),
    )
    for title, field in sections:
        lines.extend(_list_section(title, summary[field]))
    lines.extend([f"<!-- conversation:{session_id}:end -->", ""])
    return "\n".join(lines)


def _replace_managed_section(content: str, session_id: str, rendered: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf"<!-- conversation:{re.escape(session_id)}:start -->.*?"
        rf"<!-- conversation:{re.escape(session_id)}:end -->\n?",
        re.DOTALL,
    )
    if pattern.search(content):
        updated = pattern.sub(lambda _match: rendered, content, count=1)
    else:
        updated = content.rstrip() + "\n\n" + rendered
    normalized = updated.rstrip() + "\n"
    return normalized, normalized != content


def _remove_managed_section(path: Path, session_id: str) -> None:
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"\n?<!-- conversation:{re.escape(session_id)}:start -->.*?"
        rf"<!-- conversation:{re.escape(session_id)}:end -->\n?",
        re.DOTALL,
    )
    updated = pattern.sub("\n", content, count=1).rstrip() + "\n"
    if updated != content:
        _write_text(path, updated)


def _prune(output: Path, index: dict, current_day: date, retention_days: int | None) -> list[str]:
    if retention_days is None:
        return []
    cutoff = current_day - timedelta(days=retention_days - 1)
    removed: list[str] = []
    for candidate in output.iterdir():
        if not candidate.is_file() or not DAILY_FILE_PATTERN.fullmatch(candidate.name):
            continue
        file_day = date.fromisoformat(candidate.stem)
        if file_day < cutoff:
            candidate.unlink()
            removed.append(candidate.name)
    if removed:
        index["sessions"] = [
            entry for entry in index["sessions"] if entry.get("file") not in removed
        ]
    return sorted(removed)


def record_summary(args: argparse.Namespace) -> dict:
    project = _project_root(args.project)
    policy = load_policy(project)
    if not policy.exists or policy.cadence == "off":
        raise ValueError("Conversation archive is disabled; configure manual, daily, or weekly first")

    raw = (
        sys.stdin.buffer.read().decode("utf-8-sig")
        if args.input == "-"
        else Path(args.input).read_text(encoding="utf-8-sig")
    )
    raw = raw.lstrip("\ufeff")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Summary input must be a JSON object")
    summary = _validate_summary(payload)

    output = _output_path(project, policy.output_directory)
    output.mkdir(parents=True, exist_ok=True)
    index = _load_index(output)
    archive_day = date.fromisoformat(summary["date"])
    daily_file = output / f"{archive_day.isoformat()}.md"
    initial = f"# 会话纪要 {archive_day.isoformat()}\n"
    current = daily_file.read_text(encoding="utf-8") if daily_file.exists() else initial
    rendered = _render_session(summary)
    updated, changed = _replace_managed_section(current, summary["session_id"], rendered)

    existing = next(
        (entry for entry in index["sessions"] if entry.get("session_id") == summary["session_id"]),
        None,
    )
    moved = bool(existing and existing.get("file") != daily_file.name)
    if moved:
        _remove_managed_section(output / existing["file"], summary["session_id"])
        changed = True
    if changed or not daily_file.exists():
        _write_text(daily_file, updated)

    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "session_id": summary["session_id"],
        "date": summary["date"],
        "file": daily_file.name,
        "transcript_path": summary["transcript_path"],
        "updated_at": now,
    }
    index_changed = existing is None or changed or moved
    if existing:
        if index_changed:
            index["sessions"] = [
                entry if item.get("session_id") == summary["session_id"] else item
                for item in index["sessions"]
            ]
    else:
        index["sessions"].append(entry)

    index["sessions"] = sorted(
        index["sessions"], key=lambda item: (item.get("date", ""), item.get("session_id", ""))
    )
    removed = _prune(output, index, archive_day, policy.retention_days)
    index_path = output / "index.json"
    if index_changed or removed or not index_path.exists():
        index["updated_at"] = now
        _write_text(index_path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    return {
        "recorded": True,
        "changed": changed or index_changed,
        "session_id": summary["session_id"],
        "file": str(daily_file),
        "index": str(index_path),
        "pruned": removed,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure = subparsers.add_parser("configure", help="write the project archive policy")
    configure.add_argument("--project", required=True)
    configure.add_argument("--cadence", choices=sorted(ALLOWED_CADENCES), required=True)
    configure.add_argument("--output-directory")
    configure.add_argument(
        "--retention-days",
        type=int,
        help="days to retain; use 0 for unlimited retention",
    )
    configure.set_defaults(handler=configure_project)

    due = subparsers.add_parser("due", help="check whether an enabled archive is due")
    due.add_argument("--project", required=True)
    due.add_argument("--date", help="override the local date for deterministic checks")
    due.set_defaults(handler=archive_due)

    record = subparsers.add_parser("record", help="write a redacted JSON summary")
    record.add_argument("--project", required=True)
    record.add_argument("--input", required=True, help="JSON file path or '-' for stdin")
    record.set_defaults(handler=record_summary)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"[ERROR] {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
