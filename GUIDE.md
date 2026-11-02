# ai-skill 使用教程

> 3 种用法，从最简单到最完整。

---

## 用法 1：最简单——直接丢文件（适用于任何 AI）

把 `RULES.md` 的内容复制粘贴给任何 AI，或者说一句：

```
请读取 /path/to/ai-skill/RULES.md 并遵守里面的规则来帮我编码
```

就这样。**ChatGPT、Claude、Gemini、通义、文心、Copilot Chat、任何AI 都能用。**

---

## 用法 2：Codex 即插即用（推荐）

首次安装两个全局入口：

```powershell
python /path/to/ai-skill/scripts/install-codex.py
```

开始一个新 Codex 任务后，直接说：

```text
把 /path/to/ai-skill 接入 /path/to/your-project
```

`$ai-skill-bootstrap` 会识别两个路径、检查项目技术栈并完成接入。也可以直接运行：

```bash
python /path/to/ai-skill/scripts/init-project.py --path 你的项目路径 --ide codex
```

跑完之后你的项目里会多出这些文件：

```
你的项目/
├── RULES.md                        ← 万能入口（所有 AI 通用）
├── CLAUDE.md                       ← Claude Code 自动读
├── .cursorrules                    ← Cursor 自动读
├── .github/copilot-instructions.md ← GitHub Copilot 自动读
├── .windsurf/rules/ai-skill.md     ← Windsurf 自动读
├── .kiro/rules/ai-skill.md         ← Kiro 自动读
├── AGENTS.md                       ← OpenAI Codex 自动读
├── .agents/skills/                 ← Codex 原生专项 skills，按需加载
├── .ai-skill/framework/            ← 可移植的完整规则快照
├── .ai-skill/project/              ← 项目画像、偏好、决策、坑位和配方
└── GEMINI.md                       ← Gemini 自动读
```

接入完成后，新 Codex 任务会自动读取 `AGENTS.md`，并按任务匹配 `.agents/skills/`。当前任务若在接入前已启动，需要显式读取新入口一次。

### 跨项目定期治理

在 `governance/projects.json` 注册自己的软件项目后，可以运行：

```powershell
python /path/to/ai-skill/scripts/project_governance.py audit
python /path/to/ai-skill/scripts/project_governance.py sync --dry-run
python /path/to/ai-skill/scripts/project_governance.py sync
```

`audit` 只审计本机上的项目，状态写入 `governance/state/<机器>.json`，其他机器的项目标为 `not-local` 并原样保留（见 [多机器治理](docs/multi-machine-governance.md)）。只记录注册知识文件的变化和中央托管区漂移。单项目完整证据即可形成候选；第二个项目的独立证据只提高置信度。候选经用户批准并写入中央 canonical 文件后，`sync` 才会下发，且只处理 `sync_approved: true` 的项目。

### 项目会话纪要

首次接入项目时，`$ai-skill-bootstrap` 会先询问一次会话归档频率：关闭、手动、每日或每周，然后自动完成配置。你不需要手工编辑 JSON，也不需要运行 PowerShell。重复接入时会保留原选择。

直接运行初始化器时，也可以显式传入选择：

```powershell
python /path/to/ai-skill/scripts/init-project.py --path /path/to/your-project --ide codex --conversation-archive daily
```

周期可选 `off`、`manual`、`daily`、`weekly`，策略位于 `.ai-skill/project/conversation-archive.json`，纪要默认写入 `.ai-skill/project/conversations/`。定时 automation 只处理显式启用且已到期的项目。项目内不保存原始消息、凭据或完整 JSONL；原始会话备份必须单独选择项目外的私有目录。

### 只想配某个 IDE？

```bash
# 只配 Claude Code
python /path/to/ai-skill/scripts/init-project.py --path . --ide claude-code

# 只配 Cursor
python /path/to/ai-skill/scripts/init-project.py --path . --ide cursor
```

---

## 用法 3：手动配置（不想跑脚本的情况）

### Claude Code
把 `RULES.md` 复制到项目根目录，改名为 `CLAUDE.md`。

### Cursor
把 `RULES.md` 复制到项目根目录，改名为 `.cursorrules`。

### Windsurf
把 `RULES.md` 复制到 `.windsurf/rules/ai-skill.md`。

### GitHub Copilot
把 `RULES.md` 复制到 `.github/copilot-instructions.md`。

### VS Code (任何 AI 扩展)
在对话框第一句说：`请读取项目根目录的 RULES.md 并遵守`。

### Kiro
把 `RULES.md` 复制到 `.kiro/rules/ai-skill.md`。

### OpenAI Codex
推荐运行初始化器。只复制 `AGENTS.md` 会加载基础规则，但不会让完整分类库进入 Codex 原生 skill 发现机制。

### 其他任何 AI
直接把 `RULES.md` 的内容贴过去就行。

---

## 不需要命令，AI 自动判断

你不需要记任何斜杠命令。RULES.md 里的"自动路由"规则会让 AI 自动判断：

| 你怎么说 | AI 自动做什么 |
|---------|-------------|
| "帮我改这个 bug" | 先写复现测试 → 定位根因 → 最小修复 → 验证 |
| "帮我规划一下这个功能" | 复述需求 → 列假设 → 拆步骤 → 等你确认 |
| "帮我检查一下这段代码" | 逐项审查：正确性/安全/范围/简洁 → 输出报告 |
| "构建失败了" | 读错误 → 定位第一个错误 → 精准修复 → 重新验证 |
| "帮我写测试" | TDD 流程：写失败测试 → 最小实现 → 重构 |
| 普通编码请求 | 遵守五原则直接执行 |

**你只需要正常说话，AI 自动选择合适的任务处理方式。** 正式工作流系统仅在你明确要求或继续已启用工作流时使用，普通 Skill 接入不会追问工作流。

---

## Claude Code 专属功能（可选）

如果你用的是 Claude Code，有两个额外功能可以用（**不是必须的**）：

### 功能 1：Claude Code Slash Commands

把 `commands/` 目录复制到项目的 `.claude/commands/` 下：

```bash
mkdir -p .claude/commands
cp /path/to/ai-skill/commands/*.md .claude/commands/
```

然后在 Claude Code 里可以打 `/plan` `/tdd` `/review` `/build-fix` `/learn` 来触发预设流程。

**但你不用这些命令也完全可以**——正常说话 AI 会自动走对应流程。

### 功能 2：Claude Code Hooks

把 hooks 配置合并到 `.claude/settings.json`：

```json
{
  "permissions": {
    "allow": [
      "Read(**/ai-skill/**)",
      "Read(**/RULES.md)"
    ]
  }
}
```

这让 Claude Code 可以自动读取 skill 文件而不用每次弹权限确认。

---

## Skill 库扩展

如果 RULES.md 的精简版不够用，Codex 会从 `.agents/skills/` 按任务描述加载对应 skill；其他 AI 可读取完整源文件：

```
/path/to/ai-skill/skills\
├── foundations\languages\python.md      Python 完整规范
├── foundations\languages\typescript.md   TypeScript 完整规范
├── foundations\languages\go.md          Go 完整规范
├── foundations\git-conventions.md       Git 完整规范
├── foundations\error-handling.md        错误处理完整规范
├── foundations\security-basics.md       安全完整规范
├── quality\code-review.md              代码审查完整规范
├── quality\testing.md                  测试完整规范
├── knowledge\pitfalls.md               踩坑记录（持续增长）
└── knowledge\recipes.md                操作配方（持续增长）
```

你可以告诉 AI：`读取 /path/to/ai-skill/skills/knowledge/pitfalls.md 看看有没有类似的坑`。

---

## 常见问题

**Q: 我需要编辑什么配置文件吗？**
A: 不需要。`init-project.py` 跑完就能用。RULES.md 是通用的，不需要按项目修改。

**Q: 我用的 AI 工具不在上面的列表里怎么办？**
A: 把 RULES.md 的内容粘贴给它，或者告诉它读取 RULES.md 文件。任何能读文本的 AI 都能用。

**Q: 我想加项目特有的规则怎么办？**
A: 写入 `.ai-skill/project/context.md`、`zones.md`、`preferences.md` 或 `decisions.md`；这些文件不会被框架同步覆盖。

**Q: 问题、Bug、解法和我的习惯会自动归纳吗？**
A: 会在任务收尾时由 `$project-knowledge-evolution` 判断。Bug 必须有已验证根因和修复；明确偏好可直接记录，行为推断至少需要两个独立任务证据。无持久价值时不会改知识库。

**Q: 怎么新增一个语言的规范？**
A: 修改中央 `skills/` 单一源并运行 `python scripts/compile-targets.py`，由编译器生成 `.agents/skills/<id>/SKILL.md`。
