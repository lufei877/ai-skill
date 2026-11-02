#!/usr/bin/env python3
"""Build and install the local ai-skill Codex plugin."""
from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
from pathlib import Path

from plugin_version import update_plugin_cachebuster

SKILL_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_ROOT = SKILL_ROOT / "codex"
MARKETPLACE_NAME = "ai-skill-local"
PLUGIN_NAME = "ai-skill-governance"
PLUGIN_ROOT = MARKETPLACE_ROOT / "plugins" / PLUGIN_NAME


def run(command: list[str]) -> None:
    """Run one installation command and fail with its output visible."""
    subprocess.run(command, check=True, cwd=SKILL_ROOT)


def codex_command(*args: str) -> list[str]:
    """Resolve the executable npm shim safely on Windows."""
    executable = shutil.which("codex.cmd" if os.name == "nt" else "codex")
    if executable is None:
        raise FileNotFoundError("Codex CLI was not found on PATH")
    if os.name == "nt" and executable.lower().endswith(".cmd"):
        return ["cmd.exe", "/d", "/c", executable, *args]
    return [executable, *args]


def main() -> None:
    run([sys.executable, "-X", "utf8", "-B", str(SKILL_ROOT / "scripts" / "compile-targets.py")])
    version = update_plugin_cachebuster(PLUGIN_ROOT)
    print(f"[INFO] Content-bound plugin version: {version}")

    marketplace_output = subprocess.run(
        codex_command("plugin", "marketplace", "list"),
        check=True,
        cwd=SKILL_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    if MARKETPLACE_NAME not in marketplace_output:
        run(codex_command("plugin", "marketplace", "add", str(MARKETPLACE_ROOT)))

    run(codex_command("plugin", "add", f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"))
    installed = json.loads(subprocess.run(
        codex_command("plugin", "list", "--marketplace", MARKETPLACE_NAME, "--json"),
        check=True, cwd=SKILL_ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout)
    expected_id = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
    if not any(
        entry.get("pluginId") == expected_id
        and entry.get("version") == version
        and entry.get("enabled") is True
        for entry in installed.get("installed", [])
    ):
        raise RuntimeError("Codex did not report the expected enabled plugin version")

    if os.name == "nt":
        subprocess.run(
            ["setx", "AI_SKILL_HOME", str(SKILL_ROOT)],
            check=True,
            capture_output=True,
            text=True,
        )
    print(f"[OK] Installed {PLUGIN_NAME}@{MARKETPLACE_NAME}")
    print(f"[OK] AI_SKILL_HOME={SKILL_ROOT} (available to new processes)")
    print("[INFO] Start a new Codex task to pick up the installed skills.")


if __name__ == "__main__":
    main()
