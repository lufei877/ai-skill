---
description: ai-skill 框架自动加载工作流
---

# /load-skills

## 触发条件
每次接到编码任务时自动执行（或用户手动 `/load-skills`）。

## 步骤

### 1. 加载核心规则
读取以下文件并内化五项原则 + 约束守则：
- `{ai-skill-root}/core/principles.md`
- `{ai-skill-root}/core/constraints.md`
- `.ai-skill/context.md`（项目信息）
- `.ai-skill/zones.md`（文件分区）

### 2. 按任务类型匹配 skill
根据用户请求中的关键词，匹配 skill 的 trigger 字段：
- Git 操作 → `foundations/git-conventions.md`
- 错误处理 → `foundations/error-handling.md`
- 安全 → `foundations/security-basics.md`
- 审查 → `quality/code-review.md`
- 测试 → `quality/testing.md`
- 项目级 skill 优先

### 3. 检查冻结区
确认要修改的文件不在冻结区。涉及冻结区 → 停下询问用户。

### 4. 执行任务
遵守已加载 skill 的所有规则。

### 5. 完成后自检
按 constraints.md 自检清单逐项检查。

### 6. 进化检查
遇到新问题/新模式 → 按 evolution/protocol.md 追加记录。
