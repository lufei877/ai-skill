#!/usr/bin/env python3
"""
learn-from-git.py — 从 git 历史中自动提取项目约定并生成 skill。

灵感来源：everything-claude-code 的 git 历史驱动 skill 生成。

用法:
    python /path/to/ai-skill/scripts/learn-from-git.py               # 分析当前目录
    python /path/to/ai-skill/scripts/learn-from-git.py --path /repo   # 分析指定仓库
    python /path/to/ai-skill/scripts/learn-from-git.py --write        # 分析并写入 skill 文件
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


def run_git(cmd: str, cwd: Path) -> str:
    """运行 git 命令并返回输出。"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd, encoding="utf-8"
        )
        return result.stdout.strip()
    except Exception:
        return ""


def analyze_commit_style(cwd: Path) -> dict:
    """分析 commit message 风格。"""
    log = run_git("git log --oneline -50", cwd)
    if not log:
        return {"style": "unknown", "samples": []}

    lines = log.splitlines()
    conventional = 0
    for line in lines:
        # 去掉 hash
        msg = line.split(" ", 1)[1] if " " in line else line
        if re.match(r"^(feat|fix|docs|style|refactor|test|chore|perf|ci)(\(.*?\))?:", msg):
            conventional += 1

    ratio = conventional / len(lines) if lines else 0
    style = "conventional-commits" if ratio > 0.5 else "freeform"

    return {
        "style": style,
        "conventional_ratio": f"{ratio:.0%}",
        "total_analyzed": len(lines),
        "samples": [l.split(" ", 1)[1] for l in lines[:5] if " " in l],
    }


def analyze_file_patterns(cwd: Path) -> dict:
    """分析常见文件模式。"""
    # 查看最近改动最多的文件
    freq = run_git("git log --pretty=format: --name-only -100", cwd)
    if not freq:
        return {}

    files = [f for f in freq.splitlines() if f.strip()]
    counter = Counter(files)

    # 按扩展名统计
    ext_counter = Counter()
    for f in files:
        p = Path(f)
        if p.suffix:
            ext_counter[p.suffix] += 1

    return {
        "hottest_files": [f for f, _ in counter.most_common(10)],
        "language_distribution": dict(ext_counter.most_common(10)),
    }


def analyze_branch_strategy(cwd: Path) -> str:
    """分析分支策略。"""
    branches = run_git("git branch -r", cwd)
    if not branches:
        return "unknown"

    branch_names = [b.strip() for b in branches.splitlines()]
    has_develop = any("develop" in b for b in branch_names)
    has_release = any("release" in b for b in branch_names)

    if has_develop and has_release:
        return "git-flow"
    elif has_develop:
        return "github-flow-with-develop"
    else:
        return "github-flow (trunk-based)"


def generate_report(cwd: Path) -> str:
    """生成分析报告。"""
    lines = [
        f"# Git History Analysis: {cwd.name}",
        "",
    ]

    # Commit 风格
    commit_info = analyze_commit_style(cwd)
    lines.append("## Commit Style")
    lines.append(f"- Pattern: **{commit_info['style']}**")
    if commit_info.get("conventional_ratio"):
        lines.append(f"- Conventional Commits ratio: {commit_info['conventional_ratio']}")
    if commit_info.get("samples"):
        lines.append("- Recent samples:")
        for s in commit_info["samples"]:
            lines.append(f"  - `{s}`")
    lines.append("")

    # 文件模式
    file_info = analyze_file_patterns(cwd)
    if file_info.get("language_distribution"):
        lines.append("## Language Distribution (by recent changes)")
        for ext, count in sorted(file_info["language_distribution"].items(), key=lambda x: -x[1]):
            lines.append(f"- `{ext}`: {count} changes")
        lines.append("")

    if file_info.get("hottest_files"):
        lines.append("## Hottest Files (most frequently changed)")
        for f in file_info["hottest_files"]:
            lines.append(f"- `{f}`")
        lines.append("")

    # 分支策略
    branch = analyze_branch_strategy(cwd)
    lines.append("## Branch Strategy")
    lines.append(f"- Detected: **{branch}**")
    lines.append("")

    # 建议
    lines.append("## Suggested Actions")
    if commit_info["style"] == "conventional-commits":
        lines.append("- [OK] Project uses Conventional Commits, git-conventions skill is compatible")
    else:
        lines.append("- [SUGGEST] Consider adopting Conventional Commits (see skills/foundations/git-conventions.md)")

    return "\n".join(lines)


def write_project_skill(cwd: Path, report: str) -> None:
    """将分析结果写入项目的 .ai-skill/ 目录。"""
    ai_dir = cwd / ".ai-skill"
    ai_dir.mkdir(parents=True, exist_ok=True)

    dst = ai_dir / "git-analysis.md"
    dst.write_text(report, encoding="utf-8")
    print(f"[OK] Written to {dst}")


def main():
    parser = argparse.ArgumentParser(description="从 git 历史分析项目约定")
    parser.add_argument("--path", type=str, default=".", help="仓库路径")
    parser.add_argument("--write", action="store_true", help="写入到 .ai-skill/")
    args = parser.parse_args()

    cwd = Path(args.path).resolve()

    # 检查是否是 git 仓库
    if not (cwd / ".git").exists():
        print(f"[ERROR] {cwd} is not a git repository")
        sys.exit(1)

    report = generate_report(cwd)
    print(report)

    if args.write:
        write_project_skill(cwd, report)


if __name__ == "__main__":
    main()
