---
name: conversation-archive
description: Create redacted, recoverable project conversation summaries and manage project-local archive cadence. Use when the user asks to preserve, summarize, restore, back up, or periodically archive Codex conversations, session IDs, decisions, changed files, unresolved work, next steps, or explicit working preferences in a project. 排除普通聊天摘要、原始凭据或未授权的跨项目会话导出。
---

# Conversation Archive

Store a compact recovery record in the project without copying raw Codex transcripts into the repository.

## Respect The Policy

Read `<project>/.ai-skill/project/conversation-archive.json` before scheduled work.

- Treat a missing policy as `off`.
- Support only `off`, `manual`, `daily`, and `weekly`.
- Let `manual` archive only on an explicit request.
- Let `daily` or `weekly` automation continue only when `due` reports `true`.
- Keep the output directory inside the project. Default to `.ai-skill/project/conversations`.
- Do not copy raw JSONL transcripts into the project. Configure raw transcript backup separately, only to an explicit private external directory.

Resolve `<archive-skill>` to the absolute directory containing this loaded `SKILL.md`. Use its bundled script from any working directory; do not look for `scripts/archive_conversation.py` under the business project or central library root. Resolve `<project>` separately to the target project's absolute path.

```powershell
python -X utf8 -B "<archive-skill>/scripts/archive_conversation.py" configure --project "<project>" --cadence daily
python -X utf8 -B "<archive-skill>/scripts/archive_conversation.py" due --project "<project>"
```

## Build The Summary

Use current conversation context and verified workspace evidence. If a transcript path is available, use it only as a source and record its path; do not embed raw messages.

Create one JSON object with:

- `session_id`: current Codex session ID;
- `date`: local `YYYY-MM-DD` archive date;
- `transcript_path`: optional original JSONL location;
- `goals`: user goals and discussed topics;
- `confirmed_facts`: verified facts and accepted wording;
- `decisions`: confirmed product or engineering decisions;
- `changed_files`: files actually changed;
- `unresolved_items`: incomplete work and known limits;
- `next_steps`: concrete continuation steps;
- `user_preferences`: only explicit preferences or independently repeated stable habits.

Do not include secrets, credentials, cookies, tokens, full prompts, raw message text, speculative root causes, or unverified conclusions. Use `未提供` or an empty list when evidence is unavailable; do not invent it.

## Record And Recover

Pass the JSON to the script. Use `--input -` for stdin or a JSON file path:

```powershell
python -X utf8 -B "<archive-skill>/scripts/archive_conversation.py" record --project "<project>" --input "<summary-json-absolute-path>"
```

The script writes one Markdown file per day and updates `index.json`. Re-recording the same session replaces its managed section instead of duplicating it.

To resume after context loss:

1. Read the newest daily Markdown files and `index.json`.
2. Confirm unresolved items against current source and runtime state.
3. Use the recorded session ID and transcript path only when deeper reconstruction is necessary.
4. State which facts came from the archive and may now be stale.

## Coordinate With Knowledge Evolution

Keep conversation recovery separate from durable project rules. After the task is complete, invoke `$project-knowledge-evolution` only for verified, reusable lessons. A conversation summary is evidence for later review, not automatic approval to change the knowledge base.

## 输出契约

交付脱敏纪要路径、索引与归档频率状态；说明恢复范围和未保存的材料，不声称完整恢复原始会话。
