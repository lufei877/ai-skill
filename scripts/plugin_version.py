"""Bind the local plugin version to its generated, installable contents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def plugin_content_version(plugin_root: Path) -> str:
    """Return a deterministic build ID, excluding runtime caches and itself."""
    manifest_path = plugin_root / ".codex-plugin/plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current = manifest.pop("version", None)
    if not isinstance(current, str) or not current:
        raise ValueError(f"Plugin manifest has no valid version: {manifest_path}")
    base = current.split("+", 1)[0]
    files = {}
    for path in sorted(plugin_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(plugin_root)
        if path.suffix == ".pyc" or {"__pycache__", ".pytest_cache", ".git"}.intersection(relative.parts):
            continue
        content = path.read_bytes()
        if path == manifest_path:
            content = json.dumps(
                {**manifest, "version": base}, sort_keys=True, ensure_ascii=False
            ).encode("utf-8")
        files[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return f"{base}+codex.{digest[:16]}"


def update_plugin_cachebuster(plugin_root: Path) -> str:
    """Update only when installable content changed; repeated builds are stable."""
    version = plugin_content_version(plugin_root)
    path = plugin_root / ".codex-plugin/plugin.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["version"] != version:
        manifest["version"] = version
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return version
