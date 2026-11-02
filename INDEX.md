# ai-skill 索引

> 由 `python scripts/sync.py` 自动生成
> 共 30 个中央原生 Skill；不含 core 规则、生成副本和独立安装的第三方 Skill。

中央维护者：ai-skill。生成位置：`.agents/skills/<name>/`；具体来源与分组如下。

项目选装记录与托管摘要分别位于 `.ai-skill/project/skill-selection.json` 和 `managed-skills.json`。

## 需求库

听到「需求库」或「用需求库里的 X」（例如「用需求库里的卡密登录」），先读 [requirements/README.md](requirements/README.md)，按卡片中文名称或英文文件名匹配；未匹配时报告尚未入库，多张匹配时请用户选择。

需求卡存需求和验收证据，不计入原生 Skill 数量；按卡确认项目边界与待确认事项，再生成测试、编写实现。

## 基础工程与治理 (core) — 30 个

| Skill | 类型 | 权威源码 |
| --- | --- | --- |
| `ai-build-fix` | workflow | [commands/build-fix.md](commands/build-fix.md) |
| `ai-finish` | workflow | [commands/finish.md](commands/finish.md) |
| `ai-grill` | workflow | [commands/grill.md](commands/grill.md) |
| `ai-learn` | workflow | [commands/learn.md](commands/learn.md) |
| `ai-plan` | workflow | [commands/plan.md](commands/plan.md) |
| `ai-review` | workflow | [commands/review.md](commands/review.md) |
| `ai-skill-bootstrap` | native | [codex/skills/ai-skill-bootstrap/SKILL.md](codex/skills/ai-skill-bootstrap/SKILL.md) |
| `ai-tdd` | workflow | [commands/tdd.md](commands/tdd.md) |
| `code-review` | guidance | [skills/quality/code-review.md](skills/quality/code-review.md) |
| `complexity-review` | guidance | [skills/quality/complexity-review.md](skills/quality/complexity-review.md) |
| `conversation-archive` | native | [codex/skills/conversation-archive/SKILL.md](codex/skills/conversation-archive/SKILL.md) |
| `cross-project-skill-governance` | native | [codex/skills/cross-project-skill-governance/SKILL.md](codex/skills/cross-project-skill-governance/SKILL.md) |
| `desktop-operations-architecture` | guidance | [skills/architecture/desktop-operations-architecture.md](skills/architecture/desktop-operations-architecture.md) |
| `desktop-release` | native | [codex/skills/desktop-release/SKILL.md](codex/skills/desktop-release/SKILL.md) |
| `engineering-decision-boundaries` | guidance | [skills/foundations/engineering-decision-boundaries.md](skills/foundations/engineering-decision-boundaries.md) |
| `error-handling` | guidance | [skills/foundations/error-handling.md](skills/foundations/error-handling.md) |
| `flow` | workflow | [commands/flow.md](commands/flow.md) |
| `git-conventions` | guidance | [skills/foundations/git-conventions.md](skills/foundations/git-conventions.md) |
| `health` | native | [codex/skills/health/SKILL.md](codex/skills/health/SKILL.md) |
| `hunt` | native | [codex/skills/hunt/SKILL.md](codex/skills/hunt/SKILL.md) |
| `lang-go` | guidance | [skills/foundations/languages/go.md](skills/foundations/languages/go.md) |
| `lang-python` | guidance | [skills/foundations/languages/python.md](skills/foundations/languages/python.md) |
| `lang-typescript` | guidance | [skills/foundations/languages/typescript.md](skills/foundations/languages/typescript.md) |
| `pitfalls` | guidance | [skills/knowledge/pitfalls.md](skills/knowledge/pitfalls.md) |
| `project-knowledge-evolution` | native | [codex/skills/project-knowledge-evolution/SKILL.md](codex/skills/project-knowledge-evolution/SKILL.md) |
| `recipes` | guidance | [skills/knowledge/recipes.md](skills/knowledge/recipes.md) |
| `security-basics` | guidance | [skills/foundations/security-basics.md](skills/foundations/security-basics.md) |
| `skill-factory` | native | [codex/skills/skill-factory/SKILL.md](codex/skills/skill-factory/SKILL.md) |
| `testing` | guidance | [skills/quality/testing.md](skills/quality/testing.md) |
| `verification-evidence-ladder` | guidance | [skills/quality/verification-evidence-ladder.md](skills/quality/verification-evidence-ladder.md) |
