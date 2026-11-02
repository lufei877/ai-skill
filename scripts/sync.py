#!/usr/bin/env python3
"""
sync.py — 扫描 skill 库，生成索引，并同步到各 IDE 入口文件。

用法:
    python scripts/sync.py                  # 扫描并生成索引
    python scripts/sync.py --check          # 仅检查是否需要更新
    python scripts/sync.py --stats          # 显示 skill 库统计信息
    python scripts/sync.py --health         # 进化健康度报告
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

from codex_support import native_skill_catalog

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = SKILL_ROOT / "skills"
EVOLUTION_DIR = SKILL_ROOT / "evolution"


def discover_all_skills() -> list[dict[str, str]]:
    """扫描中央规范、命令与原生 Skill，排除生成副本。"""
    return native_skill_catalog(SKILL_ROOT)


def generate_index(skills: list[dict[str, str]]) -> str:
    """生成统一中央清单，不将 core 文件或分发副本重复计数。"""
    lines = [
        "# ai-skill 索引", "", "> 由 `python scripts/sync.py` 自动生成",
        f"> 共 {len(skills)} 个中央原生 Skill；不含 core 规则、生成副本和独立安装的第三方 Skill。",
        "", "中央维护者：ai-skill。生成位置：`.agents/skills/<name>/`；具体来源与分组如下。",
        "", "项目选装记录与托管摘要分别位于 `.ai-skill/project/skill-selection.json` 和 `managed-skills.json`。",
        "", "## 需求库",
        "", "听到「需求库」或「用需求库里的 X」（例如「用需求库里的卡密登录」），先读 "
        "[requirements/README.md](requirements/README.md)，按卡片中文名称或英文文件名匹配；"
        "未匹配时报告尚未入库，多张匹配时请用户选择。",
        "", "需求卡存需求和验收证据，不计入原生 Skill 数量；按卡确认项目边界与待确认事项，再生成测试、编写实现。",
    ]
    for group, title in (("core", "基础工程与治理"),):
        entries = [skill for skill in skills if skill["group"] == group]
        lines.extend(["", f"## {title} ({group}) — {len(entries)} 个", "", "| Skill | 类型 | 权威源码 |", "| --- | --- | --- |"])
        for skill in entries:
            lines.append(f"| `{skill['name']}` | {skill['kind']} | [{skill['source']}]({skill['source']}) |")
    return "\n".join(lines) + "\n"


def show_stats(skills: list[dict[str, str]]) -> None:
    """显示中央与当前安装集合的不同口径。"""
    print(f"[STATS] Central skills: {len(skills)}")
    for group, count in sorted(Counter(skill["group"] for skill in skills).items()):
        print(f"  - {group}: {count}")
    central = {skill["name"] for skill in skills}
    installed = {path.parent.name for path in (SKILL_ROOT / ".agents/skills").glob("*/SKILL.md")}
    print(f"  Installed: {len(installed)}")
    print(f"  Independent/unmanaged: {', '.join(sorted(installed - central)) or 'none'}")
    print(f"  Missing central: {', '.join(sorted(central - installed)) or 'none'}")


def missing_knowledge_fields(entry: str) -> list[str]:
    """Require labeled metadata values, not incidental mentions in prose."""
    fields = (("scope", "范围"), ("evidence", "证据"), ("verified_at", "日期"), ("status", "状态"))
    return [
        english for english, chinese in fields
        if not re.search(
            rf"^(?:[-*]\s+)?(?:\*\*|`)?(?:{english}|{chinese})(?:\*\*|`)?\s*[:：]\s*\S",
            entry, re.MULTILINE,
        )
    ]


def health_report() -> None:
    """进化健康度报告。"""
    print("\n[HEALTH] 进化健康度报告:")

    # 统计 pitfalls
    pitfalls_file = SKILLS_DIR / "knowledge" / "pitfalls.md"
    pit_count = 0
    if pitfalls_file.exists():
        pit_count = len(re.findall(r"^### PIT-", pitfalls_file.read_text(encoding="utf-8"), re.MULTILINE))
    print(f"  踩坑记录: {pit_count} 条")

    # 统计 recipes
    recipes_file = SKILLS_DIR / "knowledge" / "recipes.md"
    rec_count = 0
    if recipes_file.exists():
        rec_count = len(re.findall(r"^### RECIPE-", recipes_file.read_text(encoding="utf-8"), re.MULTILINE))
    print(f"  操作配方: {rec_count} 条")

    # 统计进化日志
    log_file = EVOLUTION_DIR / "log.md"
    evo_count = 0
    if log_file.exists():
        evo_count = len(re.findall(r"^### EVO-", log_file.read_text(encoding="utf-8"), re.MULTILINE))
    print(f"  进化日志: {evo_count} 条")

    # Static evidence completeness is observable; reuse effectiveness is not.
    for filename, marker in (("pitfalls.md", "PIT"), ("recipes.md", "RECIPE")):
        source = SKILLS_DIR / "knowledge" / filename
        if not source.exists():
            continue
        entries = re.split(r"^### " + marker + r"-", source.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]
        incomplete = []
        for entry in entries:
            if missing_knowledge_fields(entry):
                incomplete.append(entry.splitlines()[0])
        print(f"  {filename}: {len(incomplete)}/{len(entries)} entries lack evidence metadata")
        for title in incomplete:
            print(f"    - {title}")
    print("  Reuse, recurrence and model benefit: unknown without execution records")
    print("  Duplicate or misplaced knowledge: requires semantic review; counts are not quality scores")


def main():
    parser = argparse.ArgumentParser(description="ai-skill 同步与管理工具")
    parser.add_argument("--check", action="store_true", help="仅检查")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    parser.add_argument("--health", action="store_true", help="健康度报告")
    args = parser.parse_args()

    skills = discover_all_skills()
    print(f"发现 {len(skills)} 个 skill")

    if args.stats:
        show_stats(skills)
        return

    if args.health:
        health_report()
        return

    # 生成索引
    index_content = generate_index(skills)
    index_path = SKILL_ROOT / "INDEX.md"

    if args.check:
        if index_path.exists() and index_path.read_text(encoding="utf-8") == index_content:
            print("[OK] 索引已同步")
        else:
            print("[NEED UPDATE] 索引需要更新，运行: python scripts/sync.py")
            sys.exit(1)
        return

    index_path.write_text(index_content, encoding="utf-8")
    print(f"[OK] 已写入 {index_path}")


if __name__ == "__main__":
    main()
