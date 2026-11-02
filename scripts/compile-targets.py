#!/usr/bin/env python3
"""
compile-targets.py — Target Compiler（目标编译器）

把唯一源 RULES.md（中性 IR）编译到各 AI 编码平台的原生载体文件，
保证语义一致、杜绝手抄漂移。思路源自 yao-meta-skill 的 Target Compiler。

用法:
    python scripts/compile-targets.py            # 编译并写入所有载体
    python scripts/compile-targets.py --check    # 仅检查是否漂移，漂移则非零退出
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from codex_support import (
    deploy_framework,
    framework_files,
    mirror_drift,
    mirror_payloads,
    native_skill_payloads,
    payload_drift,
    sync_payloads,
)
from skill_factory import validate_skill_text
from library_release import check_core
from plugin_version import plugin_content_version, update_plugin_cachebuster

SKILL_ROOT = Path(__file__).resolve().parent.parent
SOURCE = SKILL_ROOT / "RULES.md"

BANNER = "<!-- 此文件由 scripts/compile-targets.py 从 RULES.md 自动生成，请勿手改；改 RULES.md 后重跑编译。-->"


@dataclass
class Target:
    """一个平台载体的编译目标。"""

    name: str           # 平台名（仅日志用）
    path: str           # 相对仓库根的输出路径
    frontmatter: str = ""  # 平台专属 frontmatter（如 Cursor .mdc）


# 各平台原生载体。body 统一为 RULES.md，仅 frontmatter/路径按平台差异化。
TARGETS: list[Target] = [
    Target("Codex",          "AGENTS.md"),
    Target("Cursor (旧)",     ".cursorrules"),
    Target(
        "Cursor (新)",
        ".cursor/rules/ai-skill.mdc",
        frontmatter=(
            "---\n"
            "description: AI 编码规范（先想再写/极简/精准手术/目标驱动），所有编码任务自动遵守\n"
            "globs:\n"
            "alwaysApply: true\n"
            "---\n"
        ),
    ),
    Target("Gemini",         "GEMINI.md"),
    Target("Copilot",        ".github/copilot-instructions.md"),
    Target("Kiro",           ".kiro/rules/ai-skill.md"),
    Target("Windsurf",       ".windsurf/rules/ai-skill.md"),
]


def render(target: Target, body: str) -> str:
    """渲染单个载体的完整内容。"""
    return f"{target.frontmatter}{BANNER}\n\n{body}"


COMMANDS_DIR = SKILL_ROOT / "commands"
CLAUDE_COMMANDS_DIR = SKILL_ROOT / ".claude" / "commands"
CODEX_SKILLS_DIR = SKILL_ROOT / ".agents" / "skills"
PLUGIN_ROOT = SKILL_ROOT / "codex" / "plugins" / "ai-skill-governance"


def compile_commands(*, check: bool) -> list[str]:
    """把 commands/*.md 编译到 .claude/commands/（Claude Code 原生斜杠命令）。

    返回漂移的文件列表（仅 check 模式有意义）。
    """
    if not COMMANDS_DIR.exists():
        return []

    drifted: list[str] = []
    cmd_files = sorted(COMMANDS_DIR.glob("*.md"))

    for src in cmd_files:
        dst = CLAUDE_COMMANDS_DIR / src.name
        content = src.read_text(encoding="utf-8")

        if check:
            current = dst.read_text(encoding="utf-8") if dst.exists() else None
            if current != content:
                drifted.append(str(dst.relative_to(SKILL_ROOT)))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
            print(f"[OK] {'command':12s} -> .claude/commands/{src.name}")

    return drifted


def compile_codex_skills(*, check: bool) -> list[str]:
    """Compile canonical sources to repo and plugin native skills."""
    payloads = native_skill_payloads(SKILL_ROOT)
    plugin_payloads = {
        relative: content
        for relative, content in payloads.items()
        if relative.parts[0]
        in {
            "ai-skill-bootstrap",
            "conversation-archive",
            "cross-project-skill-governance",
            "project-knowledge-evolution",
            "flow",
            "skill-factory",
            "health",
            "hunt",
        }
    }
    destinations = [
        (CODEX_SKILLS_DIR, payloads, False),
        (PLUGIN_ROOT / "skills", plugin_payloads, True),
    ]
    drifted: list[str] = []
    for destination, destination_payloads, mirror in destinations:
        if check:
            checker = mirror_drift if mirror else payload_drift
            drifted.extend(checker(destination, destination_payloads))
        else:
            writer = mirror_payloads if mirror else sync_payloads
            writer(destination, destination_payloads)
            print(f"[OK] Codex skills -> {destination.relative_to(SKILL_ROOT)}")

    framework_destination = PLUGIN_ROOT / "assets" / "framework"
    if check:
        expected_root = SKILL_ROOT
        for source in framework_files(SKILL_ROOT):
            output = framework_destination / source.relative_to(expected_root)
            if not output.exists() or output.read_bytes() != source.read_bytes():
                drifted.append(str(output))
        source = SKILL_ROOT / "scripts/project_governance.py"
        output = framework_destination / "scripts/project_governance.py"
        if not output.exists() or output.read_bytes() != source.read_bytes():
            drifted.append(str(output))
    else:
        deploy_framework(SKILL_ROOT, framework_destination)
        source = SKILL_ROOT / "scripts/project_governance.py"
        (framework_destination / "scripts/project_governance.py").write_bytes(source.read_bytes())
        print(f"[OK] Codex plugin framework -> {framework_destination.relative_to(SKILL_ROOT)}")
    manifest = PLUGIN_ROOT / ".codex-plugin/plugin.json"
    if check:
        installed_version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        if installed_version != plugin_content_version(PLUGIN_ROOT):
            drifted.append(str(manifest))
    else:
        print(f"[OK] Plugin version -> {update_plugin_cachebuster(PLUGIN_ROOT)}")
    return drifted


def main() -> None:
    parser = argparse.ArgumentParser(description="把 RULES.md 编译到各平台原生载体")
    parser.add_argument("--check", action="store_true", help="仅检查漂移，不写入")
    args = parser.parse_args()

    if not SOURCE.exists():
        sys.exit(f"[ERROR] 找不到源文件 {SOURCE}")
    body = SOURCE.read_text(encoding="utf-8")
    check_core(SKILL_ROOT)

    contract_errors = [
        f"{path}: {error}"
        for path, content in native_skill_payloads(SKILL_ROOT).items()
        if path.name == "SKILL.md"
        for error in validate_skill_text(content)
    ]
    if contract_errors:
        sys.exit("[CONTRACT] Central skill validation failed:\n" + "\n".join(contract_errors))

    drifted: list[str] = []
    for target in TARGETS:
        out_path = SKILL_ROOT / target.path
        content = render(target, body)

        if args.check:
            current = out_path.read_text(encoding="utf-8") if out_path.exists() else None
            if current != content:
                drifted.append(target.path)
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"[OK] {target.name:12s} -> {target.path}")

    # 编译 commands/ → .claude/commands/
    cmd_drifted = compile_commands(check=args.check)
    drifted.extend(cmd_drifted)
    drifted.extend(compile_codex_skills(check=args.check))

    if args.check:
        if drifted:
            print("[DRIFT] 以下载体与源文件不一致，运行: python scripts/compile-targets.py")
            for p in drifted:
                print(f"  - {p}")
            sys.exit(1)
        print("[OK] 所有载体均与源文件一致")
        return

    print(
        f"[DONE] 已编译 {len(TARGETS)} 个平台载体 + "
        f"{len(list(COMMANDS_DIR.glob('*.md')))} 个斜杠命令 + Codex 原生 skills"
    )


if __name__ == "__main__":
    main()
