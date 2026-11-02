# ai-skill — AI 编码规范框架

> 让 AI 编码助手在你的项目中遵守统一规范、自动学习、持续进化。
> 适配 Codex / Claude Code / Cursor / VS Code / Windsurf / GitHub Copilot。

## 核心特性

| 特性 | 说明 |
|------|------|
| **五项原则** | 融合 Karpathy 四原则 + 实战"问题即知识"原则 |
| **分类 Skill** | foundations / quality / architecture / business / deployment / knowledge |
| **按需路由** | 按目标、作用域和排除边界选择 Skill，关键词只作检索提示 |
| **证据驱动进化** | 自动归纳已验证 Bug、解法、流程、决策和稳定偏好 |
| **多 IDE** | 一键初始化，所有 IDE 看到一致的规则 |
| **项目隔离** | 分组选装，托管摘要保护项目修改，同名冲突保留整个 Skill 包 |
| **Codex 原生** | `AGENTS.md` + `.agents/skills` 渐进加载 + 可安装 plugin |
| **会话恢复** | 按项目选择手动、每日或每周保存脱敏纪要，原始 transcript 默认不入项目 |

## 1 分钟上手

```bash
# 安装或更新治理插件的按需入口
python /path/to/ai-skill/scripts/install-codex.py

# 之后可直接在 Codex 中给出路径；或运行：
python /path/to/ai-skill/scripts/init-project.py --path 你的项目路径 --ide codex

# 生成所有 IDE 入口（默认生成全部）
python /path/to/ai-skill/scripts/init-project.py --path 你的项目路径 --ide all

# 只生成 Claude Code 入口
python /path/to/ai-skill/scripts/init-project.py --path 你的项目路径 --ide claude-code
```

Codex 初始化后：

1. `AGENTS.md` 自动加载基础规则，已有项目内容不会被覆盖。
2. `.agents/skills/` 按任务描述自动加载完整专项规则。
3. `.ai-skill/project/detected.md` 自动记录静态识别的技术栈和命令。
4. `.ai-skill/project/` 保存项目偏好、决策、坑位和配方，后续同步不会覆盖。

中央原生 Skill 的完整来源见 `INDEX.md`。公开版只包含 `core` 分组。选择保存在 `.ai-skill/project/skill-selection.json`。

项目 Skill 的中央托管摘要保存在 `.ai-skill/project/managed-skills.json`。未被本地修改的文件可以升级；同名冲突会保留整个包并报告 `CONFLICT`。旧项目优先从更新前的框架快照辨认旧生成内容，来源未知的同名文件不会被强行接管。解决冲突时先对比项目版本与中央源码，手动合并或明确替换；不要删除托管记录来绕过保护。独立安装的第三方 Skill 保留，不计入中央契约通过率。

当前任务在接入前已经启动时，需要显式读取新入口；新 Codex 任务会自动发现。

`compile-targets.py` 根据插件实际包内容生成稳定的版本摘要：内容不变时版本不变，规则或随包资源变化时版本随之变化，`--check` 同时检查该摘要。`install-codex.py` 使用 Codex 官方安装入口并核对安装后的启用版本；本机插件更新与业务项目稳定版下发是两个独立动作。独立项目的 `.ai-skill/framework/` 包含初始化器和工厂脚本，命令使用解析后的绝对路径，不依赖中央库仍在原机器。

## 目录结构

```
ai-skill/
├── core/                  核心规则（每次任务必读）
│   ├── principles.md      五项核心原则
│   ├── constraints.md     AI 改代码守则
│   ├── zones.md           文件分区规则
│   └── context-template.md 项目宪法模板
├── skills/                分类 Skill 库
│   ├── foundations/       基础规范（git, 错误处理, 安全）
│   ├── quality/           质量保障（review, 测试）
│   ├── architecture/      架构层
│   ├── business/          业务层
│   ├── deployment/        部署层
│   └── knowledge/         增量知识（pitfalls, recipes）
├── router.md              智能路由
├── evolution/             自我进化引擎
├── hooks/                 各 IDE 钩子配置
├── scripts/               工具脚本
├── codex/                 原生 skills、plugin 与 marketplace
├── .agents/skills/        编译生成的 repo-scoped Codex skills
└── INDEX.md               自动生成的索引
```

## 五项核心原则

1. **先想再写** — 先取证，说明重要假设，只澄清影响目标和风险的缺口
2. **极简优先** — 最少代码解决问题，零投机
3. **精准手术** — 只动必须动的，匹配已有风格
4. **目标驱动** — 定义可验证的成功标准，循环验证
5. **问题即知识** — 踩坑记录到 pitfalls，模式记录到 recipes

## 管理命令

```bash
# 查看 skill 库统计
python scripts/sync.py --stats

# 进化健康度报告
python scripts/sync.py --health

# 重新生成索引
python scripts/sync.py

# 检查索引是否同步
python scripts/sync.py --check

# 把 RULES.md 编译到各平台原生载体（Codex/Cursor/Gemini/Copilot/Kiro/Windsurf）
python scripts/compile-targets.py

# 检查载体是否漂移（改完规则后在本地运行）
python scripts/compile-targets.py --check
```

## 软件与 Agent 体检

`$health` 默认覆盖 **Agent 配置、软件安全防御、代码腐化与可维护性** 三条线，也可直接说“用 health 只查安全”或“检查这个项目的屎山问题”。它属于 `core` 组；源码在 `codex/skills/health/`，编译到 `.agents/skills/health/` 和治理插件包。Agent 线保留 Codex/Claude 指令、Skill 重复候选、Hook/MCP 与验证入口检查。

体检先建立软件地图和覆盖台账，再追代码与调用链，检查认证授权、注入、文件/网络边界、桌面 IPC、秘密与依赖风险，以及耦合、重复事实、过期兼容、错误降级、状态和测试真实性。大文件或关键词命中只算线索，不默认打分；确认问题必须有触发条件、具体位置、现有防护与缺口、最小修法和验证方式。

两个只读采集器使用 Python 3.11+ 标准库，不执行源码、配置命令或历史采集；软件清单不代表漏洞扫描或完成语义审查。Agent 复核时按已有授权选择必要的隔离验证，体检默认交付报告，不自动修复。来源综合固定版本 [Waza Health](https://github.com/tw93/Waza/tree/8b2c3560ba0b174a5c984b75e4417d5c2e7453f8/skills/health) 与用户提供的代码审计包，固定哈希和 MIT 许可见 [来源说明](codex/skills/health/references/provenance.md)。

```powershell
python -X utf8 -B codex/skills/health/scripts/collect_health.py "<项目路径>"
# 仅检查项目侧材料
python -X utf8 -B codex/skills/health/scripts/collect_health.py "<项目路径>" --project-only
# 软件文件清单（非漏洞结论）
python -X utf8 -B codex/skills/health/scripts/collect_software.py "<项目路径>"
```

输出 JSON 只提供线索，报告须区分文件清单、源码语义审查、运行验证和依赖公告核查，并列出排除项、预算截断及未查路径。这里的 `$health` 与 `scripts/sync.py --health`（知识进化元数据统计）用途不同。新增源码及本地编译不等于宿主安装更新、稳定发布或向已有项目下发。

## 故障定位与审查

`$hunt` 属于 `core` 组，处理一般业务故障、崩溃、版本回归和反复修不好的问题。可直接说“用 hunt 定位这个问题并修复”或“只分析原因，先不要改代码”。它以复现、可证伪假设和运行证据收敛根因，按需要检查相关位置；构建问题仍优先 `ai-build-fix`，Agent 配置体检优先 `health`。

现有 `code-review` 补充发现质量、现有保护和同类缺陷复核，`skill-factory` 与 `desktop-release` 补充安装路径和随包资源验收。采用固定版本 [Waza Hunt / Check](https://github.com/tw93/Waza/tree/8b2c3560ba0b174a5c984b75e4417d5c2e7453f8/skills) 的相关方法，许可随受影响包保留；不再新增同义 `check` 入口。源码/包检查、宿主安装发现与模型实际效果分别报告。

## Skill 工厂

本库提供一个轻量的 `skill-factory` 原生入口，用于把可重复工作流整理成可维护的 Skill 包。它复用现有的规则单一源、Codex 原生分发、测试和知识进化，不引入另一套 Skill OS。

```bash
# 在明确的空目录创建最小 Skill 包
python scripts/skill_factory.py scaffold <目录> --name <skill-name> --description "..."

# 检查 Skill 契约
python scripts/skill_factory.py validate <skill目录>

# 刚生成的模板只检查结构；填写实际契约后再运行默认校验
python scripts/skill_factory.py validate <skill目录> --level structure

# 全量检查中央 Skill，编译器也执行相同契约检查
python scripts/skill_factory.py validate-library

# 用正例、反例和近邻请求做确定性触发冒烟检查
python scripts/skill_factory.py trigger-eval <skill目录> --cases <trigger_cases.json>
```

共享 Skill 至少应有清晰的触发边界、可验证的输出契约，并把长说明和确定性逻辑分别放到 `references/` 与 `scripts/`。涉及打包、发布、权限或外部平台时，继续使用对应的验证和治理流程，不由工厂命令隐式执行。

结构、契约、词语冒烟和真实模型效果是四类证据。词语匹配不能判断否定或跨语言语义，模板通过结构检查也不代表可以生产使用。代表性中文与混合语言任务及对照方法见 [模型评测协议](docs/skill-model-evaluation.md)。本轮没有真实模型对照结果，不宣称速度、成本或准确率提升。

> **单一源原则**：规范只在 `RULES.md` 里改，再跑 `compile-targets.py` 把变更编译到
> `AGENTS.md`（Codex）、`.cursorrules` + `.cursor/rules/ai-skill.mdc`（Cursor 旧+新）、
> `GEMINI.md`、`.github/copilot-instructions.md`、`.kiro/`、`.windsurf/`。各载体顶部带
> "自动生成"提示，请勿手改。

## 自我进化

AI 在工作中遇到以下情况会触发进化判断：
- 已验证 Bug 与修复 → 项目 `pitfalls.md`
- 可重复多步流程 → 项目 `recipes.md`
- 用户明确偏好或重复行为证据 → `preferences.md`
- 产品/架构决定 → `decisions.md`
- 单项目完整证据 → 生成中央候选
- 多项目重复验证 → 提高候选置信度

普通文件变化不会自动生成知识。跨会话定时归纳使用 Codex automation；单任务收尾由 `$project-knowledge-evolution` 判断，有持久价值才写入。

首次用 `$ai-skill-bootstrap` 接入项目时，只需选择会话归档频率，写入 `.ai-skill/project/conversation-archive.json`；重复接入保留原选择。普通 Skill 接入不询问或启用工作流，已有工作流配置保持不变。明确需要工作流时再使用 `$flow`，按需确认系统身份和能力模式；详细契约集中在该入口。项目内只保存结构化脱敏纪要和索引，默认写入 `.ai-skill/project/conversations/`，原始 Codex JSONL 需另行备份到私有外部目录。

进化日志记录在 `evolution/log.md`。

## 致谢

- [Andrej Karpathy](https://x.com/karpathy/status/2015883857489522876) — LLM 编码四原则
- douxuanpro — 实战踩坑经验与框架设计
