#!/usr/bin/env python3
"""Collect bounded, read-only Agent configuration evidence (Python 3.11+)."""
from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
import re
import shutil
import sys
import tomllib
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".cache"}


def read_text(path: Path, scope: str) -> tuple[str | None, dict]:
    """Read bounded UTF-8 text; error messages never include file contents."""
    record = {"path": str(path), "scope": scope, "status": "ok"}
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None, {**record, "status": "too_large"}
        record["bytes"] = len(raw)
        return raw.decode("utf-8-sig"), record
    except FileNotFoundError:
        return None, {**record, "status": "missing"}
    except (OSError, UnicodeError) as error:
        return None, {**record, "status": "unreadable", "error": type(error).__name__}


def load_config(path: Path, scope: str) -> tuple[dict | None, dict]:
    text, record = read_text(path, scope)
    if text is None:
        return None, record
    try:
        data = tomllib.loads(text) if path.suffix == ".toml" else json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Expected an object")
        return data, record
    except (ValueError, RecursionError) as error:
        return None, {**record, "status": "invalid", "error": type(error).__name__}


def normalized_path(value: str) -> str:
    """Compare Windows spelling variants without corrupting POSIX case."""
    if re.match(r"^[A-Za-z]:[/\\]", value) or value.startswith(("\\\\", "//")):
        return ntpath.normcase(ntpath.normpath(value))
    return os.path.normcase(os.path.realpath(value))


def instruction(path: Path, scope: str) -> dict:
    text, record = read_text(path, scope)
    if text is None:
        return record
    start, end = "<!-- ai-skill:start -->", "<!-- ai-skill:end -->"
    counts = text.count(start), text.count(end)
    record["managed_block"] = (
        "none" if counts == (0, 0) else
        "present" if counts == (1, 1) and text.index(start) < text.index(end) else
        "malformed"
    )
    # Only an explicit standalone import outside fenced examples is a signal.
    fenced = False
    imports = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and re.fullmatch(r"\s*@(?:\./)?AGENTS\.md\s*", line):
            imports.append(number)
    record["agents_reference"] = (
        "explicit_import_signal" if imports else
        "mention_only" if "AGENTS.md" in text else "none"
    )
    record["import_lines"] = imports
    record["runtime_loading"] = "unverified"
    return record


def mcp_summary(servers: object) -> list[dict]:
    if not isinstance(servers, dict):
        return [{"state": "invalid_configuration", "runtime": "unverified"}]
    records = []
    for name, server in sorted(servers.items()):
        if not isinstance(server, dict):
            records.append({"name": name, "state": "invalid_configuration", "runtime": "unverified"})
            continue
        command = server.get("command")
        executable = "not_applicable"
        if isinstance(command, str) and command:
            if command.startswith(("\\\\", "//")):
                executable = "network_path_unverified"
            elif Path(command).is_absolute():
                executable = "found" if Path(command).is_file() else "missing"
            elif ntpath.isabs(command) or "/" in command or "\\" in command:
                executable = "relative_unverified"
            else:
                executable = "found_on_collector_path" if shutil.which(command) else "not_on_collector_path"
        records.append({
            "name": name,
            "state": "disabled" if server.get("enabled") is False or server.get("disabled") is True else "configured",
            "transport": "stdio" if command else "remote" if server.get("url") else "unknown",
            "executable": executable,
            "runtime": "unverified",
        })
    return records


def codex_config(path: Path, project: str, scope: str) -> dict:
    data, record = load_config(path, scope)
    if data is None:
        return {**record, "project_trust": "unverified", "mcp": []}
    projects = data.get("projects", {})
    matches = []
    if isinstance(projects, dict):
        for name, settings in projects.items():
            if normalized_path(name) == normalized_path(project):
                level = settings.get("trust_level") if isinstance(settings, dict) else None
                matches.append(level if level in ("trusted", "untrusted") else "unknown")
    record["project_trust"] = (
        "invalid_configuration" if not isinstance(projects, dict) else
        "no_exact_entry" if not matches else
        matches[0] if len(set(matches)) == 1 else "conflicting_entries"
    )
    record["trust_scope"] = "exact_path_only; effective_runtime_trust_unverified"
    record["mcp"] = mcp_summary(data.get("mcp_servers", {}))
    for field, allowed in {
        "approval_policy": {"never", "on-request", "on-failure", "untrusted"},
        "sandbox_mode": {"read-only", "workspace-write", "danger-full-access"},
    }.items():
        value = data.get(field)
        record[field] = value if isinstance(value, str) and value in allowed else "unspecified_or_custom"
    budget = data.get("project_doc_max_bytes")
    record["project_doc_max_bytes"] = budget if type(budget) is int and budget >= 0 else None
    record["effective_config"] = "unverified; profiles, parents and runtime overrides not merged"
    return record


def json_config(path: Path, scope: str, project: str | None = None) -> dict:
    data, record = load_config(path, scope)
    if data is None:
        return record
    is_settings = path.name in {"settings.json", "settings.local.json"}
    record["misplaced_mcp_servers"] = is_settings and "mcpServers" in data
    record["mcp"] = [] if is_settings else mcp_summary(data.get("mcpServers", {}))
    if path.name == ".claude.json" and project is not None:
        record["project_mcp"] = []
        projects = data.get("projects", {})
        record["project_entries"] = "exact_path_only"
        if isinstance(projects, dict):
            for name, local in projects.items():
                if normalized_path(name) == normalized_path(project):
                    servers = local.get("mcpServers", {}) if isinstance(local, dict) else None
                    record["project_mcp"].append({
                        "scope": "project", "mcp": mcp_summary(servers),
                    })
        else:
            record["project_entries"] = "invalid_configuration"
    hooks = data.get("hooks", {})
    record["hook_event_count"] = len(hooks) if isinstance(hooks, dict) else None
    permissions = data.get("permissions", {})
    record["permission_entry_counts"] = {
        kind: len(permissions[kind]) if isinstance(permissions.get(kind), list) else None
        for kind in ("allow", "ask", "deny")
    } if isinstance(permissions, dict) else None
    record["effective_config"] = "unverified; settings overlays not merged"
    return record


def skill_inventory(roots: list[Path], max_directories: int = 4000) -> dict:
    """Inventory explicit trees, deduplicating physical packages across roots."""
    packages: dict[str, dict] = {}
    scopes = []
    for root in roots:
        scope = {
            "path": str(root), "status": "complete_within_scope",
            "directories": 0, "gaps": [],
        }
        seen = set()
        pending = [root]
        while pending:
            if len(seen) >= max_directories:
                scope["gaps"].append({"reason": "directory_budget"})
                break
            directory = pending.pop()
            try:
                identity = normalized_path(str(directory.resolve()))
                if identity in seen:
                    continue
                entries = sorted(directory.iterdir(), key=lambda p: p.name)
                seen.add(identity)
                for entry in entries:
                    if entry.name == "SKILL.md" and entry.is_file():
                        text, receipt = read_text(entry, "skill_candidate")
                        if text is None:
                            scope["gaps"].append({"path": str(entry), "reason": receipt["status"]})
                            continue
                        front = re.match(
                            r"\A---\s*\n(.*?)\n---(?:\s|$)", text, re.DOTALL
                        )
                        name = re.search(
                            r"^name:\s*['\"]?([a-z0-9-]+)['\"]?\s*$",
                            front[1], re.MULTILINE,
                        ) if front else None
                        if not name:
                            scope["gaps"].append({"path": str(entry), "reason": "unsupported_or_missing_name"})
                            continue
                        key = normalized_path(str(entry.resolve()))
                        packages[key] = {
                            "path": str(entry.resolve()), "name": name[1],
                            "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        }
                    elif entry.is_dir() and entry.name not in SKIP_DIRS:
                        pending.append(entry)
            except FileNotFoundError:
                scope["gaps"].append({"path": str(directory), "reason": "missing"})
            except (OSError, RuntimeError) as error:
                scope["gaps"].append({"path": str(directory), "reason": type(error).__name__})
        scope["directories"] = len(seen)
        if scope["gaps"]:
            scope["status"] = "missing" if not seen and scope["gaps"][0]["reason"] == "missing" else "partial"
        scopes.append(scope)
    grouped: dict[str, list[dict]] = {}
    for package in packages.values():
        grouped.setdefault(package["name"], []).append(package)
    duplicates = [
        {
            "name": name, "paths": sorted(p["path"] for p in entries),
            "content": (
                "identical" if len({p["hash"] for p in entries}) == 1 else "different"
            ),
        }
        for name, entries in sorted(grouped.items()) if len(entries) > 1
    ]
    return {
        "roots": scopes, "excluded_directories": sorted(SKIP_DIRS),
        "unique_packages": len(packages), "duplicate_candidates": duplicates,
        "activation": "unverified", "plugin_caches": "not_scanned",
    }


def verifiers(project: Path) -> dict:
    data, record = load_config(project / "package.json", "project")
    scripts = data.get("scripts", {}) if data else {}
    listing = re.compile(r"(?:^|\s)--(?:list(?:-stages)?|help)(?:\s|$)|(?:^|:)list$")
    record["scripts"] = []
    if isinstance(scripts, dict):
        for name, command in sorted(scripts.items()):
            if isinstance(command, str):
                kind = (
                    "listing_hint" if listing.search(name) or listing.search(command)
                    else "declared_command"
                )
                record["scripts"].append({"name": name, "kind": kind})
    record["manifests"] = [
        name for name in (
            "pyproject.toml", "pytest.ini", "tox.ini", "Makefile", "go.mod", "Cargo.toml"
        ) if (project / name).is_file()
    ]
    record["executed"] = False
    record["coverage"] = "root_manifest_inventory_only; command implementations unverified"
    return record


def collect(
    project: Path, codex_home: Path | None, user_home: Path | None,
    extra_skill_roots: list[Path],
) -> dict:
    project = project.resolve()
    if not project.is_dir():
        raise ValueError("Project directory does not exist")
    instructions = [
        instruction(project / name, "project") for name in (
            "AGENTS.md", "AGENTS.override.md", "CLAUDE.md",
            ".github/copilot-instructions.md",
        )
    ]
    configs = [codex_config(project / ".codex/config.toml", str(project), "project")]
    configs.extend(
        json_config(project / name, "project") for name in (
            ".mcp.json", ".claude/settings.json", ".claude/settings.local.json"
        )
    )
    roots = [project / ".agents/skills", project / ".claude/skills", project / ".codex/skills"]
    if codex_home is not None:
        configs.append(codex_config(codex_home / "config.toml", str(project), "global"))
        instructions.extend(
            instruction(codex_home / name, "global")
            for name in ("AGENTS.md", "AGENTS.override.md")
        )
        roots.append(codex_home / "skills")
    if user_home is not None:
        configs.append(json_config(user_home / ".claude.json", "global", str(project)))
        configs.append(json_config(user_home / ".claude/settings.json", "global"))
        instructions.append(instruction(user_home / ".claude/CLAUDE.md", "global"))
        roots.extend([user_home / ".agents/skills", user_home / ".claude/skills"])
    return {
        "schema_version": 1, "mode": "static-summary", "project": str(project),
        "scope": {
            "instructions": (
                "listed entrypoints only; parent/nested instructions "
                "and referenced sources require review"
            ),
            "history": "not_read", "project_commands": "not_executed",
            "mcp_runtime": "not_probed",
        },
        "instructions": instructions, "configs": configs,
        "skills": skill_inventory([*roots, *extra_skill_roots]),
        "verifiers": verifiers(project),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument(
        "--project-only", action="store_true",
        help="Exclude user-level instruction/config and skill roots",
    )
    parser.add_argument(
        "--codex-home", type=Path,
        help="Use this Codex home instead of CODEX_HOME or ~/.codex",
    )
    parser.add_argument(
        "--skill-root", action="append", default=[], type=Path,
        help="Add an explicit candidate skill tree; repeatable",
    )
    args = parser.parse_args()
    if args.project_only and args.codex_home is not None:
        parser.error("--project-only cannot be combined with --codex-home")
    user_home = None if args.project_only else Path.home()
    codex_home = None
    if not args.project_only:
        codex_home = args.codex_home or Path(
            os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
        )
    try:
        report = collect(args.project, codex_home, user_home, args.skill_root)
    except (ValueError, OSError) as error:
        # Avoid dumping parser excerpts, command arguments or credentials.
        parser.exit(2, f"Unable to collect project: {type(error).__name__}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
