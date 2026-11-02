#!/usr/bin/env python3
"""Read-only source inventory for software health; never a vulnerability verdict."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import stat
import sys
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_SUFFIXES = {
    ".py", ".pyw", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue",
    ".svelte", ".go", ".rs", ".java", ".kt", ".swift", ".c", ".h", ".cpp",
    ".hpp", ".cs", ".rb", ".php", ".sh", ".ps1", ".sql", ".dart",
    ".html", ".css", ".scss",
}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "venv", "env",
    "dist", "build", "target", "coverage", ".next", ".nuxt",
}
SKIP_PATHS = {".ai-skill/framework", ".ai-skill/library-releases", ".agents/skills"}
MANIFESTS = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "pnpm-lock.yaml", "pyproject.toml", "poetry.lock", "uv.lock", "pipfile",
    "pipfile.lock", "setup.py", "setup.cfg", "go.mod", "go.sum", "cargo.toml",
    "cargo.lock", "pom.xml", "build.gradle", "composer.json", "composer.lock",
    "gemfile", "gemfile.lock", "dockerfile", "compose.yml", "docker-compose.yml",
    "makefile", "pytest.ini", "tox.ini",
}
SECRET_NAMES = {".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519"}
MAX_FILE_BYTES = 1024 * 1024


def is_within(path: str, parent: str) -> bool:
    return path == parent or path.startswith(parent + "/")


def excluded_reason(path: Path, relative: str, is_dir: bool, excludes: list[str]) -> str | None:
    if any(is_within(relative, pattern) or fnmatch.fnmatchcase(relative, pattern)
           for pattern in excludes):
        return "user_exclusion"
    name = path.name.lower()
    if (is_dir and (name in SKIP_DIRS or name.startswith(".venv"))) or relative in SKIP_PATHS:
        return "dependency_cache_or_generated"
    if name.startswith(".env") or name in SECRET_NAMES or path.suffix.lower() in {".pem", ".key", ".pfx", ".p12"}:
        return "sensitive_name"
    if not is_dir and name.endswith((".min.js", ".min.css", ".map")):
        return "generated_asset"
    return None


def kind_of(path: Path, relative: str) -> str:
    name = path.name.lower()
    if name in MANIFESTS or (name.startswith("requirements") and path.suffix == ".txt"):
        return "manifest"
    if relative.startswith(".github/workflows/"):
        return "ci_config"
    if path.suffix.lower() in SOURCE_SUFFIXES:
        return "source"
    if path.suffix.lower() in {".md", ".rst", ".txt"}:
        return "document"
    return "other"


def source_summary(path: Path, size: int, remaining_bytes: int) -> tuple[dict, int]:
    if size > MAX_FILE_BYTES:
        return {"content_status": "too_large"}, 0
    if size > remaining_bytes:
        return {"content_status": "byte_budget"}, 0
    try:
        with path.open("rb") as stream:
            raw = stream.read(min(MAX_FILE_BYTES, remaining_bytes) + 1)
        if len(raw) != size:
            return {"content_status": "changed_during_read"}, len(raw)
        text = raw.decode("utf-8-sig")
        if "\x00" in text:
            return {"content_status": "non_utf8_or_binary"}, len(raw)
        return {
            "content_status": "read", "lines": len(text.splitlines()),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }, len(raw)
    except UnicodeError:
        return {"content_status": "non_utf8_or_binary"}, len(raw)
    except OSError as error:
        return {"content_status": "unreadable", "error": type(error).__name__}, 0


def collect(
    project: Path, *, excludes: list[str] | None = None,
    max_entries: int = 20000, max_total_bytes: int = 32 * 1024 * 1024,
) -> dict:
    """Inventory bounded local files; source bytes are never emitted or executed."""
    root = project.resolve()
    if not root.is_dir() or max_entries <= 0 or max_total_bytes <= 0:
        raise ValueError("Existing project and positive budgets required")
    excludes = excludes or []
    files, excluded, errors = [], [], []
    stack = [root]
    visited = set()
    entries_seen, bytes_read = 0, 0
    truncated = None
    while stack and truncated is None:
        directory = stack.pop()
        try:
            resolved = directory.resolve()
            if not resolved.is_relative_to(root):
                excluded.append({"path": directory.relative_to(root).as_posix(), "reason": "outside_root"})
                continue
            if resolved in visited:
                continue
            visited.add(resolved)
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    if entries_seen >= max_entries:
                        truncated = "entry_budget"
                        break
                    entries_seen += 1
                    path = Path(entry.path)
                    relative = path.relative_to(root).as_posix()
                    try:
                        info = entry.stat(follow_symlinks=False)
                        reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                        if stat.S_ISLNK(info.st_mode) or reparse:
                            excluded.append({"path": relative, "reason": "link_or_reparse_point"})
                            continue
                        if not path.resolve().is_relative_to(root):
                            excluded.append({"path": relative, "reason": "outside_root"})
                            continue
                        is_dir = stat.S_ISDIR(info.st_mode)
                        reason = excluded_reason(path, relative, is_dir, excludes)
                        if reason:
                            excluded.append({"path": relative, "reason": reason})
                            continue
                        if is_dir:
                            stack.append(path)
                            continue
                        if not stat.S_ISREG(info.st_mode):
                            excluded.append({"path": relative, "reason": "non_regular_file"})
                            continue
                        kind = kind_of(path, relative)
                        parts = {part.lower() for part in path.relative_to(root).parts}
                        test = bool(parts & {"test", "tests", "__tests__", "spec", "specs"}) or path.name.startswith("test_") or any(marker in path.name for marker in (".test.", ".spec."))
                        record = {
                            "path": relative, "kind": kind, "bytes": info.st_size,
                            "role": "test_candidate" if test else "unspecified",
                            "content_status": "not_read",
                        }
                        if kind == "source":
                            summary, consumed = source_summary(path, info.st_size, max_total_bytes - bytes_read)
                            bytes_read += consumed
                            record.update(summary)
                        files.append(record)
                    except (OSError, RuntimeError) as error:
                        errors.append({"path": relative, "error": type(error).__name__})
        except (OSError, RuntimeError) as error:
            errors.append({"path": directory.relative_to(root).as_posix(), "error": type(error).__name__})
    files.sort(key=lambda item: item["path"])
    sources = [item for item in files if item["kind"] == "source"]
    readable = [item for item in sources if item["content_status"] == "read"]
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in readable:
        if item["bytes"]:
            grouped[item["sha256"]].append(item["path"])
    return {
        "schema_version": 1, "mode": "software-inventory", "project": str(root),
        "coverage": {
            "inventory": "partial" if truncated or errors else "complete_within_exclusions",
            "source_read": "partial" if truncated or errors or len(readable) != len(sources) else "complete_for_listed_sources",
            "semantic_review": "not_performed", "vulnerability_database": "not_queried",
            "commands": "not_executed", "history": "not_read",
            "truncated_reason": truncated, "entries_seen": entries_seen,
            "source_bytes_read": bytes_read,
            "limits": {"entries": max_entries, "total_bytes": max_total_bytes, "file_bytes": MAX_FILE_BYTES},
            "gitignore": "not_interpreted; inspect explicit exclusions",
            "snapshot": "live_files; not_atomic",
        },
        "files": files, "excluded": sorted(excluded, key=lambda item: item["path"]),
        "errors": errors, "kinds": dict(sorted(Counter(f["kind"] for f in files).items())),
        "largest_sources": [
            {"path": item["path"], "lines": item["lines"], "role": item["role"]}
            for item in sorted(readable, key=lambda item: (-item["lines"], item["path"]))[:20]
        ],
        "duplicate_candidates": sorted(paths for paths in grouped.values() if len(paths) > 1),
        "interpretation": "Sizes and identical bytes are review leads, not defects; no security or quality verdict.",
    }


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--exclude", action="append", default=[], help="Project-relative path/glob to omit; repeatable")
    parser.add_argument("--max-entries", type=positive_int, default=20000)
    parser.add_argument("--max-total-bytes", type=positive_int, default=32 * 1024 * 1024)
    args = parser.parse_args()
    try:
        report = collect(args.project, excludes=args.exclude, max_entries=args.max_entries, max_total_bytes=args.max_total_bytes)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, f"Unable to inventory project: {type(error).__name__}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
