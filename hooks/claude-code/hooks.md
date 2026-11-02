# Claude Code Hooks 配置指南

> 将以下 hooks 配置合并到项目的 `.claude/settings.json` 中。

## 生命周期钩子

Claude Code 支持的钩子点位（参考 everything-claude-code）：

### PreToolUse — 工具调用前
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "echo '[ai-skill] Check: target file not in frozen zone'"
        }]
      },
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "echo '[ai-skill] Check: command is safe and non-destructive'"
        }]
      }
    ]
  }
}
```

### PostToolUse — 工具调用后
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "echo '[ai-skill] Reminder: run self-check list after all changes'"
        }]
      }
    ]
  }
}
```

### SessionStart — 会话开始
在新对话开始时，建议 AI 先执行：
1. 读取 `core/principles.md` 内化五项原则
2. 读取项目的 `.ai-skill/context.md`
3. 加载所有 instincts

### PreCompact — 上下文压缩前
在上下文即将被压缩时，确保保留：
1. 当前任务的目标和验证标准
2. 已加载的 skill 列表
3. 冻结区文件列表

## 权限配置
```json
{
  "permissions": {
    "allow": [
      "Read(**/ai-skill/**)",
      "Read(**/.ai-skill/**)",
      "Glob(**/ai-skill/**)",
      "Grep(**/ai-skill/**)",
      "Read(**/commands/**)"
    ]
  }
}
```
