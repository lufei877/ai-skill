---
id: skill-router
title: Skill 智能路由
priority: critical
auto_load: true
version: 3.1
---

# Skill 智能路由

> AI 接到任务后，按本文件的路由规则自动加载对应 skill。
> 路由分四级：入口约定 → 已内联行为 → 任务意图匹配 → 按需查阅。表内词语只作例子，不是强制关键词路由器。

## 第一级：会话开始时内化（不逐文件读取）

以下内容在 RULES.md / CLAUDE.md 中已内联，AI 读完入口文件即可开始工作，
**不需要逐个打开 core/ 下的文件**：

- 五项核心原则（先想再写 / 极简优先 / 精准手术 / 目标驱动 / 问题即知识）
- 工程取舍边界（先看现状 / 成熟但不盲从 / 端到端递增 / 兼容与 workaround 有退出条件）
- 禁止事项（8 条 hard rules）
- 授权边界（RULES.md 第三节）；已有授权不重复索取
- 项目冻结区清单（优先 `.ai-skill/project/zones.md`，首次涉及对应路径时再读）

完整定义文件（`core/principles.md`, `core/constraints.md`, `core/zones.md`）仅在需要查阅细节时打开。

## 第二级：Instincts（内化为行为，不逐文件加载）

以下直觉已在 RULES.md 第四节描述，不需要额外读取 YAML 文件：

- **小问题直接修** — 遇到小障碍直接修复继续
- **先搜再改** — 动手前确认上下文
- **提交前验证** — 完成前跑测试 + 清理 debug 代码
- **大改动前确认** — 按授权与风险判断，不按文件数量或重构标签暂停
- **匹配已有风格** — 保持代码风格一致
- **从错误中学习** — 已验证知识先记入项目，获批候选才进入中央库

## 第三级：按任务类型自动匹配

根据目标、实际修改对象、已有证据和 Skill 的 `description` 选择相关能力。`trigger` 仅保留为旧平台检索提示，不能证明应加载。先选完成当前任务所需的最小集合，再按依赖补充：

| 任务类型 | 触发词示例 | 加载 skill |
|---------|-----------|-----------|
| 需求库复用 | 需求库, 用需求库里的 X, 用需求库里的卡密登录 | [requirements/README.md](requirements/README.md) → 按卡片中文名称或英文文件名匹配 |
| **语言 — Python** | python, py, django, fastapi, pytest | `foundations/languages/python.md` |
| **语言 — TypeScript** | ts, tsx, react, vue, next, node | `foundations/languages/typescript.md` |
| **语言 — Go** | go, golang, gin, fiber | `foundations/languages/go.md` |
| Git 操作 | commit, push, merge, branch | `foundations/git-conventions.md` |
| 错误处理 | try, catch, error, exception, 日志 | `foundations/error-handling.md` |
| 安全相关 | auth, password, token, 注入, XSS | `foundations/security-basics.md` |
| 工程取舍 | dependency, 依赖, 兼容, 弃用, migration, workaround, MVP, 重构, 架构 | `foundations/engineering-decision-boundaries.md` |
| 代码审查 | review, PR, 审查, 检查 | `quality/code-review.md` |
| 软件与 Agent 体检 | health, 软件安全防御, 屎山/代码腐化, 可维护性, Codex/Claude 指令漂移, Skill 重复候选, Hook/MCP 配置失效 | `$health` |
| 故障定位与回归修复 | hunt, 反复修不好, 崩溃, 偶发卡死, 更新后出错 | `$hunt` |
| 复杂度专项审查 | 过度设计, YAGNI, 不必要依赖/抽象, complexity review | `quality/complexity-review.md` |
| 测试 | test, 测试, coverage, jest, pytest | `quality/testing.md` |
| API/后端 | route, endpoint, API, 接口, 中间件 | `foundations/api-conventions.md`* |
| 数据库 | database, SQL, migration, 表, 模型 | `foundations/db-conventions.md`* |
| 部署 | deploy, docker, CI/CD, build, 打包 | `deployment/deploy-guide.md`* |
| 桌面打包与验收 | Electron/Python 安装包、版本不一致、多会话打包、桌面 CI/CD | `$desktop-release` |
| 架构 | refactor, 重构, 模块, 架构, 设计 | `architecture/design-patterns.md`* |
| Windows 桌面运营软件 | desktop, Electron, PyQt, worker, 后台任务, 稳定主键 | `architecture/desktop-operations-architecture.md` |
| 完成声明与发布 | 验收, 真实运行, 打包, release ready | `quality/verification-evidence-ladder.md` |

*标 `*` 的为扩展位，按需创建。

需求库复用先读 `requirements/README.md` 再读匹配卡；未匹配时报告尚未入库，多张匹配时请用户选择，不能把模板或来源项目的卡冒充已入库需求。复用前处理「与项目无关化」及「待确认」，不把来源项目取值当默认值；仅按已有依据且适用于目标项目的验收标准先生成测试、再写实现。分发副本缺少此目录时回到中央库的 `requirements/README.md` 查阅，不在项目 `.ai-skill/framework/` 中补写卡片。


## 第四级：遇到问题时查阅

- 遇到已知类型的问题 → 查 `skills/knowledge/pitfalls.md`
- 需要标准操作步骤 → 查 `skills/knowledge/recipes.md`
- 项目特有知识 → 查 `项目/.ai-skill/project/`
- 任务收尾有可复用证据 → 使用原生 `$project-knowledge-evolution`

## 斜杠命令

用户可直接调用预设工作流：

| 命令 | 作用 |
|------|------|
| `/grill` | 需求拷问（模糊需求 → 结构化共识） |
| `/plan` | 任务规划（原则一+四驱动） |
| `/tdd` | 测试驱动开发流程 |
| `/review` | 代码审查流程 |
| `/build-fix` | 构建失败修复 |
| `/finish` | 任务收尾（自检 → 总结 → 进化判断） |
| `/learn` | 从当前项目学习并生成 skill |

### 推荐工作流编排

复杂任务建议按四阶段推进：

```
Phase 0: /grill           → 仅在重要缺口存在或用户要求访谈时澄清
Phase 1: /plan            → 拆解步骤，定义验证标准
Phase 2: 执行             → 遵守 instincts + skill 规则编码
Phase 3: /finish          → 自检 → 总结 → 进化判断
```

简单任务可跳过 Phase 0-1，直接执行 + /finish。

## 路由匹配算法

1. 明确当前请求是解释、规划、审查还是实施，以及授权范围。
2. 用 name/description 判断能力与排除边界；避免只因通用词命中而加载。
3. 只读选中 Skill 的正文，引用资料与脚本按当前需要使用；不是所有关联 Skill 都必须加载。
4. 相同正文在会话内复用，文件发生变化或上下文失效时才重读。
5. `ai-review` 负责审查流程，`code-review` 作为完整检查标准；`complexity-review` 只在明确需要过度设计/YAGNI 专项时补充，不能替代正确性、安全和性能审查。`ai-tdd` 只负责明确要求的 TDD，`testing` 负责一般验证选择。不重复启动流程。
   一般故障由 `hunt` 组织诊断；构建、启动和依赖错误优先 `ai-build-fix`，软件安全/代码腐化或 Agent 指令/配置体检优先 `health`，纯视觉偏好使用可用 UI 能力。按实际对象选择，不仅凭“出错”二字加载所有流程。
6. 普通任务使用清单与当前会话推进。只有用户明确要求工作流或正在继续已启用的工作流时加载 `flow`；不因任务较长、多步骤或出现“流程”就引入工作流系统。

## 项目级 skill 优先

如果项目的 `.agents/skills/` 或 `.ai-skill/project/` 下有同领域规则，优先使用项目级版本。
全局 skill 作为 fallback。同步器只更新未被本地修改的中央托管包；同名冲突保留整个项目 Skill 包并报告。

中央分组与来源见 `INDEX.md`。当前公开版只含 `core` 组。

## 动态发现

如果 `trigger` 字段匹配不到任何 skill，但任务明显需要特定知识：
1. 在当前可用元数据与 `INDEX.md` 中检索相关任务，不扫描全部正文
2. 如果仍然没有匹配，正常执行任务
3. 任务完成后按项目知识归纳门槛判断；新增 Skill 要有可重复任务、稳定边界与可验收输出，不能只因一次检索失败创建
