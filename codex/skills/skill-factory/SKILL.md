---
name: skill-factory
description: Create, inspect, and validate reusable Codex skills from a repeated workflow. Use when a request is about designing a skill package, defining its trigger boundary, scaffolding files, or checking a skill before sharing. Exclude one-off prompts, ordinary project coding, and documentation-only edits.
metadata:
  short-description: Build and validate a reusable skill package
---

# Skill Factory

Use this skill to turn a repeated workflow into the smallest maintainable skill package.

## Resolve The Framework

Resolve `<ai-skill-root>` once before executing commands. Check the user-supplied library, `AI_SKILL_HOME`, the loaded plugin's `../../assets/framework`, the current project's `.ai-skill/framework`, and ancestors of the loaded skill. Require both `scripts/skill_factory.py` and `scripts/codex_support.py`; skip stale candidates. Use quoted absolute paths for the script and target from any working directory. If none exists, report the missing framework instead of running a guessed project-local `scripts/` path.

## Workflow

1. Confirm the workflow is reusable and has a concrete output contract. Keep one-off answers as ordinary work.
2. Define the job, inputs, outputs, exclusions, and the target platform before creating files.
3. Choose the lightest maturity: `scaffold` for exploration, `production` for team reuse, and `library` only when portability and maintenance evidence are required.
4. Create the explicit target with `python -X utf8 -B "<ai-skill-root>/scripts/skill_factory.py" scaffold "<target>" --name <name> --description "<description>"`; the command refuses targets inside the ai-skill source tree and refuses non-empty directories.
5. Run `python -X utf8 -B "<ai-skill-root>/scripts/skill_factory.py" validate "<target>" --level structure` for a scaffold, replace placeholders, then run contract validation without `--level structure` before sharing. Add positive, negative, and near-neighbor cases in the users' languages; lexical smoke results never establish model behavior.
6. For shared skills, run the repository's focused tests and record only verified decisions or reusable procedures through `$project-knowledge-evolution`.

## Package Contract

A reusable skill must have:

- `SKILL.md` with `name` and a discriminating `description` frontmatter field;
- a clear boundary: what should trigger and what should not;
- an output contract that another agent can verify;
- no secrets, private transcripts, or speculative rules;
- supporting scripts or references only when they remove repeated work.

Use `references/skill-factory-contract.md` for the field definitions and trigger-case format. This factory does not replace the repository's `RULES.md`, `router.md`, or platform compiler; it feeds them.

When changing a package's distribution, installer, plugin manifest, or referenced resources, use [references/installed-package-validation.md](references/installed-package-validation.md) to check the real installed surface. Source contracts, isolated file deployment, runtime discovery, and model behavior are separate evidence; validate only the layers required by the requested delivery.

## Safety Boundary

Read-only inspection can target an existing skill. Scaffold writes require an explicit target directory and refuse a non-empty directory. Package, install, release, and external network operations remain separate workflows and need their own evidence.

## 输出契约

交付可复用性判断、具体 Skill 包或检查结果；分别报告结构、契约、词语冒烟和真实模型评测状态，模板占位不得作为生产契约。
