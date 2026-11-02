---
name: project-knowledge-evolution
description: Distill verified project knowledge from completed implementation, debugging, review, build, release, or planning work. Use automatically at task closeout when reusable evidence emerged, or explicitly when the user asks to summarize, learn, evolve, record problems, bugs, fixes, workflows, decisions, or stable working preferences for the current project. 排除猜测根因、未完成修复、普通任务流水账和未经批准的中央发布。
---

# Project Knowledge Evolution

Evaluate each completed task for durable project knowledge. Do not turn ordinary task narration into permanent rules.

## Establish The Evidence

Use this priority order:

1. the user's newest explicit decision or correction;
2. current source, tests, runtime output, and reproduced behavior;
3. existing project rules and categorized knowledge;
4. completed task summaries and historical documents.

Do not record speculative root causes, incomplete work, raw conversation dumps, secrets, credentials, cookies, tokens, or unrelated-project evidence.

## Decide Whether To Write

Write only when at least one condition holds:

- a bug was reproduced, its root cause was established, and the fix was verified;
- a multi-step workflow proved reusable;
- a product or architecture decision changes future implementation choices;
- the user explicitly states or corrects a stable working preference;
- the same inferred preference appears in at least two independent tasks.

If no condition holds, make no knowledge-file changes. Mention `no durable lesson` only when the user asked for a learning report.

## Route The Finding

Use the project-local paths below. Create them from the framework templates when missing.

- Problems and bugs: `.ai-skill/project/knowledge/pitfalls.md`
- Reusable procedures: `.ai-skill/project/knowledge/recipes.md`
- Stable user preferences: `.ai-skill/project/preferences.md`
- Product and architecture decisions: `.ai-skill/project/decisions.md`
- Verified temporary complexity or compatibility debt: `.ai-skill/project/decisions.md`
- Change ledger: `.ai-skill/project/evolution/log.md`

Send a single project's complete, portable evidence to the central candidate pool with `single-project` confidence. Independent confirmation from another project raises confidence but is not required to create a candidate. Promote the candidate into the central canonical library only after explicit user approval or equivalent recorded approval. Never promote a platform-specific detail merely because it was difficult.

## Update Without Accumulating Stale Rules

Search existing entries before writing.

- Extend an existing active entry when the new evidence clarifies it.
- Add a new entry when the behavior is materially distinct.
- When a verified rule changes, mark the old entry `superseded_by` and add the replacement; do not silently rewrite history.
- Keep one canonical detailed entry and link to it from indexes or routing files.

Each entry must include:

- `scope`: project or cross-project;
- `evidence`: test, runtime, source inspection, or explicit user decision;
- `verified_at`: ISO date;
- `status`: active or superseded;
- symptom/context, root cause or decision, resolution, and prevention/verification.

For temporary complexity or compatibility debt, also record the exact location, why it must remain now, material risk, removal condition, validation evidence, and the event or date that should trigger review. Do not create a separate debt ledger or record speculative cleanup ideas.

Append a concise evolution-log item listing the changed files and evidence. Run the repository's skill/index validators afterward.

## Close Out

Report only material additions or corrections. Keep the task's normal delivery summary primary; knowledge evolution is a short final note, not a second full report.

## 输出契约

有持久证据时更新对应项目知识及演进日志，说明证据与替代关系；没有符合门槛的知识时不创建文件。
