---
name: ai-skill-bootstrap
description: Connect an existing repository to the ai-skill framework and Codex native harness. Use when the user provides an ai-skill library path or project path, asks to drop in/initialize/sync ai-skill, wants Codex to recognize a project automatically, or wants AGENTS.md plus the complete task-relevant skill library to load without manual configuration. 排除仅提供路径但没有接入意图的普通代码任务。
---

# AI Skill Bootstrap

Turn a supplied filesystem path into a working Codex project integration.

## Resolve The Paths

1. Treat a directory containing `RULES.md` and `scripts/init-project.py` as the ai-skill library.
2. Treat a directory containing source files, a package manifest, or `.git` as the target project.
3. If the user supplies only the library path, use the current workspace as the target project.
4. If the user supplies only the project path, locate the framework in this order:
   - `AI_SKILL_HOME` when configured;
   - a bundled plugin framework at `../../assets/framework` relative to this skill;
   - `<project>/.ai-skill/framework` for an existing standalone project installation;
   - an ancestor containing `RULES.md` and `scripts/init-project.py`.
5. A candidate is usable only when both `RULES.md` and `scripts/init-project.py` exist. Skip stale paths and ask for the library path only after all candidates fail. Resolve bundled paths from this loaded skill, not the process working directory.

Resolve exact absolute paths before writing. Do not initialize the ai-skill library into itself unless the user explicitly asks to rebuild its native outputs.

## Inspect Before Connecting

Read the target's existing `AGENTS.md`, package manifests, top-level directories, test/build scripts, and existing `.ai-skill` layout. Preserve project-specific instructions and knowledge.

Inspect `.ai-skill/project/skill-selection.json`. This public release ships only the `core` engineering and governance group; adding groups never removes existing skills. Ordinary business tasks should use installed specialist skills before adding a package.

Before the first write, check `<target>/.ai-skill/project/conversation-archive.json`. For conversation archiving:

- If it is missing, ask the user once to choose `off` (关闭), `manual` (手动), `daily` (每日), or `weekly` (每周).
- Explain that this choice controls only redacted project summaries; raw Codex JSONL stays outside the project by default.
- Pass the selected value to the initializer as `--conversation-archive <choice>`. Selecting `off` still records the explicit choice.
- If the policy already exists, do not ask again and do not overwrite it. Report the existing cadence.
- Do not ask the user to edit JSON or run PowerShell; the bootstrap flow performs the configuration.

Workflow is optional. During ordinary Skill setup, do not ask about it and do not create a workflow policy. Preserve an existing `<target>/.ai-skill/project/workflow-integration.json`. Only when the user explicitly requests workflow integration or continuation of an enabled workflow, read `$flow` for its system identity, capability and evidence contract. Skill access and central registration do not imply workflow activation.

Run:

```powershell
python -X utf8 -B "<ai-skill-root>/scripts/init-project.py" --path "<project-path>" --ide codex --conversation-archive <choice>
```

The initializer must:

- maintain only the marked ai-skill block inside an existing `AGENTS.md`;
- deploy the framework snapshot under `.ai-skill/framework/`;
- create or refresh `.ai-skill/project/detected.md` from repository evidence;
- preserve `.ai-skill/project/context.md`, `zones.md`, `knowledge/`, and `evolution/`;
- deploy selected Codex-native skills under `.agents/skills/` and record hashes in `.ai-skill/project/managed-skills.json`;
- preserve an entire skill package when any managed file conflicts with local edits; report each conflict, never claim full synchronization in that case. Unchanged legacy generated files can be adopted from the previous framework snapshot; unknown same-name content is preserved.

If the current conversation started before initialization, read the generated `AGENTS.md` and relevant skill files explicitly for the current turn. New Codex tasks discover them automatically.

## Verify

Run the initializer a second time and confirm it is idempotent. Then verify:

- `AGENTS.md` contains one ai-skill managed block;
- `.agents/skills/project-knowledge-evolution/SKILL.md` exists;
- `.ai-skill/framework/RULES.md` exists;
- `.ai-skill/project/detected.md` contains no unresolved placeholders;
- `.ai-skill/project/conversation-archive.json` records the selected cadence when this was a first connection;
- ordinary setup leaves a missing workflow policy absent and preserves existing policy bytes; explicit workflow requests follow `$flow`;
- project-owned knowledge files retain their prior content.

Report the detected stack, installed entry points, preserved files, and whether a new Codex task is needed to refresh startup context.

## Central Dashboard Registration

Project-local Skill installation, workflow opt-in and central dashboard registration are separate facts. Never call a project fully connected to the central dashboard merely because initialization completed or workflow routing is enabled.

When the user requests dashboard/governance access, resolve the actual central root containing `governance/projects.json` and `scripts/project_registry.py`. A bundled framework without a central registry is not that root. For an already initialized project, preserve its existing installation and policies; do not repeat initialization just to make it visible.

Register the user's exact target path from the central root:

```powershell
python scripts/project_registry.py register --path <absolute-project-path> --name <project-name>
```

Registration only updates the central project list. New entries have `sync_approved: false`, and cadence selection remains off until the user chooses it in the dashboard. Preserve existing registrations, approval flags and schedules on repeated registration. No workflow enabling, central distribution or project-file overwrite is implied.

For a missing project report, first compare the central registry with explicitly supplied paths or the available app's saved-project list. Inspect only fixed integration markers on those exact paths. A known-path snapshot can be stored as version 1 `governance/known-projects.json` with `source`, `imported_at`, and `projects: [{label, path}]`. The dashboard inspects this snapshot for unregistered candidates; it is not a live app subscription or a recursive disk search. Let the user choose candidates, or register paths they already explicitly chose. See `docs/project-cadence.md`.

## 输出契约

报告目标路径、所选 Skill 分组、安装或更新结果和保留的冲突，附幂等性与项目内容保护的验证；存在冲突不得声称完全同步。
