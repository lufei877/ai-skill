#!/usr/bin/env python3
"""Audit registered projects and distribute approved ai-skill rules."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from codex_support import (
    codex_agents_block,
    deploy_codex_project,
    framework_files,
    merge_managed_block,
    project_skill_payloads,
    sync_project_skills,
)
from library_release import require_stable_source

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = SKILL_ROOT / "governance" / "projects.json"
# Shared pre-split state; read once to seed a machine's own file, never written again.
LEGACY_STATE = SKILL_ROOT / "governance" / "state.json"
DEFAULT_AUDIT_GLOBS = (
    ".ai-skill/project/**/*.md",
    ".ai-skill/skills/**/*.md",
    "AGENTS.md",
)


@dataclass(frozen=True)
class ProjectConfig:
    """One registered project and its governance policy."""

    name: str
    path: Path
    enabled: bool
    sync_approved: bool
    audit_globs: tuple[str, ...]
    project_id: str = ""
    local: bool = True


def machine_id() -> str:
    """Name the machine whose audit and cadence state is being recorded."""
    raw = os.environ.get("AI_SKILL_MACHINE", "").strip() or socket.gethostname()
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", raw.lower()).strip("-.")
    if not cleaned:
        raise ValueError("Cannot derive a machine id; set AI_SKILL_MACHINE")
    return cleaned


def default_state_path(machine: str) -> Path:
    return SKILL_ROOT / "governance" / "state" / f"{machine}.json"


def default_report_path(machine: str) -> Path:
    return SKILL_ROOT / "governance" / "reports" / f"audit-{machine}.md"


def is_foreign_path(raw_path: str) -> bool:
    """Detect absolute paths written for the other operating system family."""
    if os.name == "nt":
        return raw_path.startswith("/") and not raw_path.startswith("//")
    return bool(PureWindowsPath(raw_path).drive) or raw_path.startswith("\\\\")


def independent_evidence_count(projects: tuple[ProjectConfig, ...], names: set[str] | list[str]) -> int:
    """Count evidence sources by project identity, so one project on two machines counts once."""
    by_name = {project.name: project.project_id for project in projects}
    return len({by_name.get(name, name) for name in names})


@dataclass(frozen=True)
class AuditProjectResult:
    """Audit outcome for one project."""

    name: str
    path: Path
    status: str
    changed_files: tuple[str, ...] = ()
    framework_drift: tuple[str, ...] = ()
    candidate_confidence: str = "none"
    project_id: str = ""


@dataclass(frozen=True)
class AuditResult:
    """Aggregate audit outcome."""

    projects: tuple[AuditProjectResult, ...]
    machine: str = ""


@dataclass(frozen=True)
class SyncProjectResult:
    """Distribution outcome for one project."""

    name: str
    path: Path
    status: str
    drift: tuple[str, ...] = ()


@dataclass(frozen=True)
class SyncResult:
    """Aggregate distribution outcome."""

    projects: tuple[SyncProjectResult, ...]


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(path: Path) -> tuple[ProjectConfig, ...]:
    """Load and validate a version-one project registry."""
    payload = _read_json(path, {})
    if payload.get("version") != 1 or not isinstance(payload.get("projects"), list):
        raise ValueError(f"Invalid project registry: {path}")

    projects: list[ProjectConfig] = []
    names: set[str] = set()
    for raw in payload["projects"]:
        name = raw.get("name")
        raw_path = raw.get("path")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every registered project needs a non-empty name")
        if name in names:
            raise ValueError(f"Duplicate project name: {name}")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"Project {name} needs a path")
        names.add(name)
        project_id = raw.get("project_id", name)
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError(f"Project {name} has an invalid project_id")

        local = not is_foreign_path(raw_path)
        if local:
            expanded = Path(os.path.expandvars(raw_path)).expanduser()
            project_path = (expanded if expanded.is_absolute() else path.parent / expanded).resolve()
        else:
            # Another OS's path: keep it verbatim, never join it onto this machine's tree.
            project_path = Path(raw_path)
        raw_globs = raw.get("audit_globs", DEFAULT_AUDIT_GLOBS)
        if not isinstance(raw_globs, list | tuple) or not all(
            isinstance(pattern, str) for pattern in raw_globs
        ):
            raise ValueError(f"Project {name} has invalid audit_globs")
        projects.append(
            ProjectConfig(
                name=name,
                path=project_path,
                enabled=bool(raw.get("enabled", True)),
                sync_approved=bool(raw.get("sync_approved", False)),
                audit_globs=tuple(raw_globs),
                project_id=project_id,
                local=local,
            )
        )
    return tuple(projects)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_signals(project: ProjectConfig) -> dict[str, str]:
    signals: dict[str, str] = {}
    project_root = project.path.resolve()
    for pattern in project.audit_globs:
        for candidate in project.path.glob(pattern):
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            try:
                relative = resolved.relative_to(project_root)
            except ValueError:
                continue
            signals[relative.as_posix()] = _hash_file(resolved)
    return dict(sorted(signals.items()))


def _managed_drift(skill_root: Path, project_path: Path) -> tuple[str, ...]:
    drift: list[str] = []
    framework_root = project_path / ".ai-skill" / "framework"
    for source in framework_files(skill_root):
        relative = source.relative_to(skill_root)
        output = framework_root / relative
        if not output.exists() or output.read_bytes() != source.read_bytes():
            drift.append(f".ai-skill/framework/{relative.as_posix()}")

    for relative, content in project_skill_payloads(skill_root, project_path).items():
        output = project_path / ".agents" / "skills" / relative
        current = output.read_text(encoding="utf-8") if output.exists() else None
        if current != content:
            drift.append(f".agents/skills/{relative.as_posix()}")

    agents_path = project_path / "AGENTS.md"
    current_agents = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    expected_agents = merge_managed_block(current_agents, codex_agents_block())
    if current_agents != expected_agents:
        drift.append("AGENTS.md#ai-skill")
    return tuple(sorted(drift))


def _write_audit_report(path: Path, result: AuditResult) -> None:
    lines = [
        "# 跨项目 Skill 审计报告",
        "",
        f"- 机器: `{result.machine}`",
        f"- 生成时间: {datetime.now(timezone.utc).isoformat()}",
        "- 候选规则: 单项目完整证据即可进入候选；跨项目重复用于提升置信度。",
        "- 计数规则: 同一 `project_id` 在多台机器上的登记只算一个独立证据来源。",
        "- 发布规则: 候选不会自动进入中央库，只有已批准并写入中央单一事实源的规则才能下发。",
        "",
    ]
    for project in result.projects:
        lines.extend(
            [
                f"## {project.name}",
                "",
                f"- 项目标识: `{project.project_id}`",
                f"- 路径: `{project.path}`",
                f"- 状态: `{project.status}`",
                f"- 中央托管区漂移: {len(project.framework_drift)}",
            ]
        )
        if project.changed_files:
            lines.extend(
                [
                    "- 候选等级: `single-project`（单项目证据候选）",
                    "- 变化文件:",
                    *[f"  - `{relative}`" for relative in project.changed_files],
                ]
            )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def audit_projects(
    skill_root: Path,
    registry_path: Path,
    state_path: Path,
    report_path: Path,
    *,
    legacy_state_path: Path | None = None,
    machine: str = "",
) -> AuditResult:
    """Audit this machine's projects without modifying them or other machines' state."""
    projects = load_registry(registry_path)
    if state_path.exists() or legacy_state_path is None:
        state = _read_json(state_path, {"version": 1, "projects": {}})
    else:
        # First run on this machine: inherit baselines of the projects that live here.
        legacy = _read_json(legacy_state_path, {"version": 1, "projects": {}}).get("projects", {})
        local_names = {project.name for project in projects if project.local}
        state = {"version": 1, "projects": {name: entry for name, entry in legacy.items() if name in local_names}}
    previous_projects = state.get("projects", {})
    # Anything not re-audited in this run keeps its previous baseline untouched.
    next_projects: dict[str, dict[str, dict[str, str]]] = dict(previous_projects)
    results: list[AuditProjectResult] = []

    for project in projects:
        if not project.enabled:
            results.append(
                AuditProjectResult(project.name, project.path, "disabled", project_id=project.project_id)
            )
            continue
        if not project.local:
            results.append(AuditProjectResult(project.name, project.path, "not-local", project_id=project.project_id))
            continue
        if not project.path.is_dir():
            results.append(AuditProjectResult(project.name, project.path, "missing", project_id=project.project_id))
            continue

        signals = _project_signals(project)
        previous = previous_projects.get(project.name)
        changed = ()
        status = "baseline"
        if isinstance(previous, dict):
            previous_files = previous.get("files", {})
            changed = tuple(
                sorted(
                    relative
                    for relative, digest in signals.items()
                    if previous_files.get(relative) != digest
                )
            )
            removed = sorted(set(previous_files) - set(signals))
            changed += tuple(f"{relative} (removed)" for relative in removed)
            status = "changed" if changed else "clean"

        next_projects[project.name] = {"files": signals}
        results.append(
            AuditProjectResult(
                name=project.name,
                path=project.path,
                status=status,
                changed_files=changed,
                framework_drift=_managed_drift(skill_root, project.path),
                candidate_confidence="single-project" if changed else "none",
                project_id=project.project_id,
            )
        )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {"version": 1, "projects": next_projects},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = AuditResult(tuple(results), machine)
    _write_audit_report(report_path, result)
    return result


def sync_projects(
    skill_root: Path,
    registry_path: Path,
    *,
    dry_run: bool,
) -> SyncResult:
    """Distribute canonical central rules to explicitly approved projects."""
    projects = load_registry(registry_path)
    if any(project.enabled and project.local and project.path.is_dir() and project.sync_approved for project in projects):
        # Deployment reads the verified snapshot, never the changing working tree.
        skill_root = require_stable_source(skill_root)
    results: list[SyncProjectResult] = []
    for project in projects:
        if not project.enabled:
            results.append(SyncProjectResult(project.name, project.path, "disabled"))
            continue
        if not project.local:
            results.append(SyncProjectResult(project.name, project.path, "not-local"))
            continue
        if not project.path.is_dir():
            results.append(SyncProjectResult(project.name, project.path, "missing"))
            continue
        if not project.sync_approved:
            results.append(
                SyncProjectResult(project.name, project.path, "skipped-not-approved")
            )
            continue

        drift = _managed_drift(skill_root, project.path)
        if not drift:
            results.append(SyncProjectResult(project.name, project.path, "current"))
            continue
        conflicts = sync_project_skills(project.path, project_skill_payloads(skill_root, project.path), dry_run=True)
        if dry_run:
            results.append(
                SyncProjectResult(project.name, project.path, "conflict" if conflicts else "would-sync", drift)
            )
            continue

        conflicts = deploy_codex_project(skill_root, project.path)
        results.append(SyncProjectResult(project.name, project.path, "conflict" if conflicts else "synced", drift))
    return SyncResult(tuple(results))


def _central_history(skill_root: Path, relative: str) -> list[bytes]:
    """Every committed version of one central file, newest first; empty without git."""
    try:
        commits = subprocess.run(
            ["git", "-C", str(skill_root), "log", "--format=%H", "--", relative],
            capture_output=True, check=True, text=True,
        ).stdout.split()
        return [
            subprocess.run(
                ["git", "-C", str(skill_root), "show", f"{commit}:{relative}"],
                capture_output=True, check=True,
            ).stdout
            for commit in commits
        ]
    except (OSError, subprocess.CalledProcessError):
        return []


def _line_delta(expected: str, current: str) -> str:
    added = removed = 0
    for line in difflib.unified_diff(expected.splitlines(), current.splitlines(), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return f"项目比中央 +{added}/-{removed} 行"


def classify_drift(skill_root: Path, project_path: Path, drift: str) -> tuple[str, str]:
    """Sort one managed-area difference into missing, outdated or project-specific."""
    if drift == "AGENTS.md#ai-skill":
        return "project-specific", "AGENTS.md 中的 ai-skill 托管区块与中央不一致"
    if drift.startswith(".ai-skill/framework/"):
        relative = drift.removeprefix(".ai-skill/framework/")
        output = project_path / drift
        if not output.exists():
            return "missing", "项目缺少该文件"
        current = output.read_bytes()
        history = _central_history(skill_root, relative)
        if current in history:
            return "outdated", f"与中央第 {history.index(current) + 1} 新的提交版本一致，项目停在旧版本"
        expected = (skill_root / relative).read_text(encoding="utf-8", errors="replace")
        return "project-specific", _line_delta(expected, current.decode("utf-8", errors="replace"))
    relative = Path(drift.removeprefix(".agents/skills/"))
    output = project_path / drift
    if not output.exists():
        return "missing", "项目缺少该文件"
    expected = project_skill_payloads(skill_root, project_path).get(relative, "")
    return "project-specific", _line_delta(expected, output.read_text(encoding="utf-8", errors="replace"))


def preview_projects(skill_root: Path, registry_path: Path, report_path: Path, *, machine: str) -> int:
    """Read-only drift preview for every local project, regardless of sync approval."""
    labels = {
        "missing": "缺失（项目停在旧版本或从未下发）",
        "outdated": "项目停在中央旧版本",
        "project-specific": "项目独有修改（可能值得回收，也可能与中央冲突，需人工比对）",
    }
    lines = [
        "# 中央托管区同步预览（只读）",
        "",
        f"- 机器: `{machine}`",
        f"- 生成时间: {datetime.now(timezone.utc).isoformat()}",
        "- 本报告不下发任何内容，也不修改 `sync_approved`。",
        "",
    ]
    total = 0
    for project in load_registry(registry_path):
        if not (project.enabled and project.local and project.path.is_dir()):
            continue
        drift = _managed_drift(skill_root, project.path)
        total += len(drift)
        grouped: dict[str, list[str]] = {key: [] for key in labels}
        for item in drift:
            category, detail = classify_drift(skill_root, project.path, item)
            grouped[category].append(f"  - `{item}`：{detail}")
        lines.extend([f"## {project.name}", "", f"- 路径: `{project.path}`",
                      f"- 同步许可: `{project.sync_approved}`", f"- 漂移总数: {len(drift)}"])
        for category, label in labels.items():
            if grouped[category]:
                lines.extend([f"- {label}: {len(grouped[category])}", *grouped[category]])
        lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return total


def _print_sync(result: SyncResult) -> None:
    for project in result.projects:
        print(f"[{project.status}] {project.name}: {project.path}")
        for drift in project.drift:
            print(f"  - {drift}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit registered projects and distribute approved ai-skill rules"
    )
    parser.add_argument(
        "command",
        choices=("audit", "sync", "preview"),
        help="Read-only audit, approved central-to-project sync, or read-only drift preview",
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--state", type=Path, help="Defaults to governance/state/<machine>.json")
    parser.add_argument("--report", type=Path, help="Defaults to governance/reports/audit-<machine>.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        machine = machine_id()
        if args.command == "audit":
            state = args.state or default_state_path(machine)
            report = args.report or default_report_path(machine)
            result = audit_projects(SKILL_ROOT, args.registry, state, report,
                                    legacy_state_path=LEGACY_STATE, machine=machine)
            print(f"[OK] Machine {machine}: audited {len(result.projects)} projects")
            print(f"[OK] Report: {report.resolve()}")
            return
        if args.command == "preview":
            report = args.report or SKILL_ROOT / "governance" / "reports" / f"sync-preview-{machine}.md"
            total = preview_projects(SKILL_ROOT, args.registry, report, machine=machine)
            print(f"[OK] Machine {machine}: {total} managed-area differences")
            print(f"[OK] Report: {report.resolve()}")
            return
        _print_sync(sync_projects(SKILL_ROOT, args.registry, dry_run=args.dry_run))
    except (ValueError, OSError) as error:
        parser.exit(1, f"[BLOCKED] {error}\n")


if __name__ == "__main__":
    main()
