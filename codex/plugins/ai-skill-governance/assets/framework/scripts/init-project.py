#!/usr/bin/env python3
"""
init-project.py - ai-skill one-click project init.

Usage:
    python /path/to/ai-skill/scripts/init-project.py                # init current dir
    python /path/to/ai-skill/scripts/init-project.py --path /path/to/project   # init specific project
    python /path/to/ai-skill/scripts/init-project.py --path . --ide cursor  # only cursor

What it does (ONE command, ZERO config):
    1. Copy RULES.md into the project (the universal entry point)
    2. Generate IDE-specific config files that point to RULES.md
    3. Done. No editing needed. Works immediately.

Supported IDEs: claude-code, cursor, vscode, windsurf, copilot, all (default)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from codex_support import (
    CONVERSATION_ARCHIVE_CADENCES,
    CONVERSATION_ARCHIVE_POLICY,
    WORKFLOW_INTEGRATION_MODES,
    WORKFLOW_MODES,
    WORKFLOW_INTEGRATION_POLICY,
    configure_conversation_archive,
    configure_workflow_integration,
    deploy_codex_project,
    select_project_skill_groups,
    SKILL_GROUPS,
    validate_workflow_system_id,
)

SKILL_ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = SKILL_ROOT / "RULES.md"
AI_SKILL_DIR = ".ai-skill"

IDE_CHOICES = ["claude-code", "cursor", "vscode", "windsurf", "copilot", "codex", "kiro", "gemini", "all"]


def copy_rules(project_path: Path) -> None:
    """Copy RULES.md into the project root."""
    dst = project_path / "RULES.md"
    if dst.resolve() == RULES_FILE.resolve():
        print(f"  = RULES.md (already in place, skipped copy)")
        return
    if dst.exists():
        print("  = RULES.md (existing project file preserved)")
        return
    shutil.copy2(RULES_FILE, dst)
    print("  + RULES.md (universal AI rules - works with ANY tool)")


def deploy_ai_skill(project_path: Path) -> None:
    """Deploy a portable framework snapshot and Codex-native skills."""
    conflicts = deploy_codex_project(SKILL_ROOT, project_path)
    for conflict in conflicts:
        print(f"  [CONFLICT] Preserved local skill package: {conflict}")
    print(f"  + {AI_SKILL_DIR}/project/ (detected profile + preserved knowledge)")
    print(f"  + {AI_SKILL_DIR}/framework/ (portable ai-skill snapshot)")
    print("  + .agents/skills/ (Codex native progressive-disclosure skills)")


def copy_commands(project_path: Path) -> None:
    """Copy commands/*.md into .claude/commands/ for native slash command support."""
    commands_src = SKILL_ROOT / "commands"
    if not commands_src.exists():
        return
    commands_dst = project_path / ".claude" / "commands"
    commands_dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in sorted(commands_src.glob("*.md")):
        shutil.copy2(src, commands_dst / src.name)
        count += 1
    if count:
        print(f"  + .claude/commands/ ({count} slash commands: /grill, /plan, /finish ...)")


def generate_claude_md(project_path: Path) -> None:
    """CLAUDE.md for Claude Code - just points to RULES.md."""
    content = f"""# CLAUDE.md

Read and follow `RULES.md` in this directory.
It contains all coding principles, constraints, and auto-routing rules.

For extended skills (language-specific rules, pitfalls, recipes):
See `{SKILL_ROOT}\\skills\\`

For evolution protocol (recording new pitfalls/recipes):
See `{SKILL_ROOT}\\evolution\\protocol.md`
"""
    (project_path / "CLAUDE.md").write_text(content, encoding="utf-8")
    copy_commands(project_path)
    print(f"  + CLAUDE.md (Claude Code)")


def generate_cursorrules(project_path: Path) -> None:
    """.cursorrules for Cursor - embeds RULES.md content."""
    rules_content = RULES_FILE.read_text(encoding="utf-8")
    (project_path / ".cursorrules").write_text(rules_content, encoding="utf-8")
    print(f"  + .cursorrules (Cursor)")


def generate_copilot(project_path: Path) -> None:
    """.github/copilot-instructions.md for GitHub Copilot."""
    github_dir = project_path / ".github"
    github_dir.mkdir(parents=True, exist_ok=True)
    rules_content = RULES_FILE.read_text(encoding="utf-8")
    (github_dir / "copilot-instructions.md").write_text(rules_content, encoding="utf-8")
    print(f"  + .github/copilot-instructions.md (GitHub Copilot)")


def generate_vscode(project_path: Path) -> None:
    """.vscode/settings.json for VS Code AI extensions."""
    vscode_dir = project_path / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings_path = vscode_dir / "settings.json"
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Existing VS Code settings preserved: JSONC or invalid JSON cannot be safely merged") from error
        if not isinstance(settings, dict):
            raise ValueError("Existing VS Code settings preserved: expected a JSON object")
    settings["ai-skill.rules"] = "RULES.md"
    settings["ai-skill.extended-skills"] = str(SKILL_ROOT / "skills")
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Also copy code snippets for quick pitfall/recipe entry
    snippets_src = SKILL_ROOT / "hooks" / "vscode" / "ai-skill.code-snippets"
    if snippets_src.exists():
        shutil.copy2(snippets_src, vscode_dir / "ai-skill.code-snippets")
    print(f"  + .vscode/settings.json + snippets (VS Code)")


def generate_windsurf(project_path: Path) -> None:
    """.windsurf/rules/ai-skill.md for Windsurf."""
    rules_dir = project_path / ".windsurf" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_content = RULES_FILE.read_text(encoding="utf-8")
    (rules_dir / "ai-skill.md").write_text(rules_content, encoding="utf-8")
    print(f"  + .windsurf/rules/ai-skill.md (Windsurf)")


# --- Additional IDE support ---

def generate_codex(project_path: Path) -> None:
    """Maintain the ai-skill block in AGENTS.md and deploy native skills."""
    deploy_ai_skill(project_path)
    print("  + AGENTS.md (preserved existing content; updated ai-skill block)")


def choose_conversation_archive_cadence(
    project_path: Path, requested: str | None
) -> str | None:
    """Ask once for a missing archive policy, or return an explicit choice."""
    policy_path = project_path / CONVERSATION_ARCHIVE_POLICY
    if policy_path.exists():
        print("  = conversation archive policy (existing choice preserved)")
        return None
    if requested is not None:
        return requested
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("  = conversation archive policy (not selected in non-interactive mode)")
        return None

    print("\n首次接入需要选择会话归档频率：")
    print("  1. off    关闭")
    print("  2. manual 手动归档")
    print("  3. daily  每日归档")
    print("  4. weekly 每周归档")
    choices = {"1": "off", "2": "manual", "3": "daily", "4": "weekly"}
    while True:
        answer = input("请选择 [1-4，直接回车为 off]: ").strip().lower()
        if not answer:
            return "off"
        cadence = choices.get(answer, answer)
        if cadence in CONVERSATION_ARCHIVE_CADENCES:
            return cadence
        print("请输入 1-4，或 off/manual/daily/weekly。")


def choose_workflow_integration(
    project_path: Path,
    requested: str | None,
    requested_system_id: str | None,
    requested_workflow_mode: str | None = None,
) -> tuple[str, str | None, str] | None:
    """Apply an explicit workflow choice; ordinary Skill setup never prompts."""
    policy_path = project_path / WORKFLOW_INTEGRATION_POLICY
    if policy_path.exists():
        print("  = workflow integration policy (existing choice preserved)")
        return None
    if requested is not None:
        default_mode = "flow-lite" if requested == "enabled" else "skill-only"
        workflow_mode = requested_workflow_mode or default_mode
        if requested == "enabled":
            validate_workflow_system_id(requested_system_id)
            if workflow_mode not in WORKFLOW_MODES or workflow_mode == "skill-only":
                raise ValueError("Enabled workflow requires flow-lite, flow-standard or flow-automated")
        elif requested != "disabled" or requested_system_id is not None or workflow_mode != "skill-only":
            raise ValueError("Disabled workflow requires no system ID and skill-only mode")
        return requested, requested_system_id, workflow_mode
    if requested_system_id is not None or requested_workflow_mode is not None:
        raise ValueError("Workflow options require an explicit --workflow-integration choice")
    return None


def generate_kiro(project_path: Path) -> None:
    """.kiro/rules/ai-skill.md for Kiro."""
    kiro_dir = project_path / ".kiro" / "rules"
    kiro_dir.mkdir(parents=True, exist_ok=True)
    rules_content = RULES_FILE.read_text(encoding="utf-8")
    (kiro_dir / "ai-skill.md").write_text(rules_content, encoding="utf-8")
    print(f"  + .kiro/rules/ai-skill.md (Kiro)")


def generate_gemini(project_path: Path) -> None:
    """GEMINI.md for Google Gemini Code Assist."""
    rules_content = RULES_FILE.read_text(encoding="utf-8")
    (project_path / "GEMINI.md").write_text(rules_content, encoding="utf-8")
    print(f"  + GEMINI.md (Gemini Code Assist)")


GENERATORS = {
    "claude-code": [generate_claude_md],
    "cursor": [generate_cursorrules],
    "copilot": [generate_copilot],
    "vscode": [generate_vscode],
    "windsurf": [generate_windsurf],
    "codex": [generate_codex],
    "kiro": [generate_kiro],
    "gemini": [generate_gemini],
    "all": [
        generate_claude_md,
        generate_cursorrules,
        generate_copilot,
        generate_vscode,
        generate_windsurf,
        generate_codex,
        generate_kiro,
        generate_gemini,
    ],
}


def main():
    parser = argparse.ArgumentParser(
        description="ai-skill: one command, zero config, works immediately"
    )
    parser.add_argument("--path", type=str, default=".", help="Target project path")
    parser.add_argument(
        "--ide", type=str, default="all", choices=IDE_CHOICES,
        help="Which IDE configs to generate (default: all)"
    )
    parser.add_argument(
        "--conversation-archive",
        choices=CONVERSATION_ARCHIVE_CADENCES,
        help="First-connect archive cadence; existing project policy is preserved",
    )
    parser.add_argument(
        "--skill-group", action="append", choices=(*SKILL_GROUPS, "all"),
        help="Add a skill group; repeat for multiple groups. New projects default to core; existing selection is preserved",
    )
    parser.add_argument(
        "--workflow-integration",
        choices=WORKFLOW_INTEGRATION_MODES,
        help="First-connect workflow routing choice; existing project policy is preserved",
    )
    parser.add_argument(
        "--workflow-system-id",
        help="Stable workflow system ID; required when workflow integration is enabled",
    )
    parser.add_argument(
        "--workflow-mode",
        choices=WORKFLOW_MODES,
        help="Workflow capability mode; existing project policy is preserved",
    )
    args = parser.parse_args()

    project_path = Path(args.path).resolve()
    if not project_path.is_dir():
        print(f"[ERROR] {project_path} is not a valid directory")
        sys.exit(1)

    print(f"\n  ai-skill init: {project_path}\n")

    archive_cadence = choose_conversation_archive_cadence(
        project_path, args.conversation_archive
    )
    try:
        workflow_integration = choose_workflow_integration(
            project_path,
            args.workflow_integration,
            args.workflow_system_id,
            args.workflow_mode,
        )
    except ValueError as error:
        parser.error(str(error))

    # Step 1: Copy RULES.md
    if args.skill_group:
        selected = list(SKILL_GROUPS) if "all" in args.skill_group else args.skill_group
        select_project_skill_groups(project_path, selected)
    copy_rules(project_path)

    # Step 2: Generate IDE configs
    print()
    for gen in GENERATORS.get(args.ide, GENERATORS["all"]):
        gen(project_path)

    if archive_cadence is not None:
        if configure_conversation_archive(project_path, archive_cadence):
            print(f"  + conversation archive policy ({archive_cadence})")

    if workflow_integration is not None:
        integration_mode, workflow_system_id, workflow_mode = workflow_integration
        try:
            created = configure_workflow_integration(
                project_path,
                integration_mode,
                workflow_system_id,
                workflow_mode,
            )
        except ValueError as error:
            parser.error(str(error))
        if created:
            detail = workflow_system_id or "no routing"
            print(f"  + workflow integration policy ({workflow_mode}: {detail})")

    print(f"\n  Done! Your project is now ai-skill enabled.")
    print(f"  Project-local Skill setup is complete.\n")
    print(f"  How to use:")
    print(f"  - Codex: AGENTS.md auto-loads; .agents/skills load by task match")
    print(f"  - Claude Code / Cursor / Windsurf / Kiro: auto-loaded on open")
    print(f"  - Other AI tools: tell it 'read RULES.md and follow it'")
    print(f"  - Chat with any AI: paste or attach RULES.md content\n")


if __name__ == "__main__":
    main()
