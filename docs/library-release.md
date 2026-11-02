# 中央 Skill 版本与防退化

本机制保障发布输入和证据可追溯，并阻止未验证的跨项目同步。它不训练模型，也不自动判断任意自然语言是否合理。具有源码写权限的人仍可修改检查器；需要通过版本评审约束，不声称这是防恶意管理员的安全隔离。

## 核心与增量

`core/behavior-contract.json` 引用现有 RULES 的五项原则、持续授权、现有技术栈和按风险验证。字面检查能发现锚点丢失，不能发现“保留原则但新增相反规则”。晋升还必须有逐项核心语义评审和真实行为证据。

每次审查增量，明确：解决的问题与证据、影响的旧规则、适用和排除场景、代价、验证方法、需要替代的内容。所有变化路径（含测试、校验器和规则）必须进入 `reviewed_paths`。不能为变绿删除测试、降低门槛、改写既有核心案例。普通发布只能追加核心案例与不变量；核心迁移需要单独设计并取得用户授权，当前命令没有跳过开关。

## 保存和验收

在中央库执行，命令中的版本号由本次实际版本决定：

```powershell
python scripts/library_release.py core
python scripts/library_release.py capture --id candidate-20260909 --expected-parent none
python scripts/library_release.py verify --id candidate-20260909
```

以后 `--expected-parent` 填操作开始时看到的稳定版本 ID。不同会话不能用旧基线覆盖新稳定版。`operation.lock` 只串行化 capture/promote/rollback；不锁编辑器。捕获前协调源码写入者，前后文件比对只检测部分竞态，不宣称原子快照。捕获失败的目录保留供排错且没有有效 manifest，换新 ID 重试；不删除或覆盖旧快照。

快照位于 `.ai-skill/library-releases/<id>/source/`，包含中央规则、原生 Skill（含无扩展名许可证和包内资源）、脚本、测试、评测输入和文档，以及 authored 插件 manifest 与 marketplace 两份入口；排除生成副本、Python/pytest/mypy/ruff 缓存和 `results` 目录。项目注册表、候选池和项目知识不作为正常发布输入。快照保存的实际内容是验收对象；新修改必须创建新候选。没有旧稳定版时第一次只证明当前核心案例通过，不宣称比旧版更好。

通过 `export` 将快照复制到独立验证目录，在那里编译生成副本，再运行契约、编译一致性和适用测试，保存原始日志；不要在保存的快照里写构建输出。测试后核对权威源码摘要仍与候选一致。执行 `evals/core-behavior-cases.json` 的全部候选案例；有稳定版时，对旧版已存在的案例在同样模型/推理配置下重跑基线。执行类任务必须在独立 fixture 中实际修改/运行并保存工具轨迹；对话类只用于结果本来就是判断的任务。由独立评审者检查轨迹和最终文件，不将验收答案预先提供给执行者。补充当前专项 Skill 的高风险案例，不能以核心小样本代替整个产品的效果评估。

核心底线要求案例通过、无越权、无无必要追问。耗时/token 可在报告中记录，但未取得实际数据就不填零；本版不对随机耗时设置任意数值门槛。

## 晋升报告格式

`promote --review <JSON文件>` 接收以下字段（这是字段说明，不能用说明代替真实记录）：

- `source_digest`：候选 manifest.digest。
- `suite_digest`：`release_digest({"suite": suite文件原始字节.hex()})`，由同一模块计算。
- `reviewer`：负责整体增量与核心语义评审的独立评审者。
- `reviewed_paths`：相对基线的全部新增、修改和删除路径；首次版本为全部文件。
- `core_review`：以核心 invariant ID 为键，全部为实际审查通过的布尔值。
- `checks`：包含不重复的 `regression`、`contracts`、`compilation`、`index` 四项，每项含 `name`、实际 `command`、`passed`、非空原始日志的 `evidence_path`。分别对应项目测试、中央契约、编译一致性和索引检查；不能用任意一个成功命令代替。
- `runs`：每例候选记录含 `case_id`、`variant=candidate`、`source_digest`、实际 `model`、`reasoning`、唯一 `run_id`、`executor`、不同于 executor 的 `reviewer`、`outcome_passed`、`unnecessary_questions`、`unauthorized_actions`、`evidence_path`。基线记录使用 `variant=baseline` 与对应旧版 digest；同案例模型与推理配置一致。

路径相对报告目录或绝对路径。工具检查完整性、绑定关系、案例覆盖、声明的结果和独立身份，并保存证据副本；无法认证身份真伪或从文件存在推断评分真实。需要可信运行轨迹与人工/独立审查，不能仅让执行者编一个“通过”JSON。

```powershell
python scripts/library_release.py promote --id candidate-20260909 --expected-parent none --review <真实评审报告.json>
python scripts/library_release.py check
python scripts/project_governance.py sync --dry-run
```

`sync` 与预览均检查稳定快照、审批证据及当前源码身份，实际下发读取验证过的快照。首次没有行为证据时保持候选并阻止下发；不提供 `force`。普通本地编译和显式初始化仍是开发工具，不代表稳定发布；不得用初始化器绕过被阻止的跨项目升级。审计功能继续可用。

## 恢复和回退

```powershell
python scripts/library_release.py export --id before-anti-regression --destination <不存在的恢复目录>
python scripts/library_release.py rollback --id <以前通过验收的版本> --expected-parent <当前稳定版本>
```

`export` 校验全部文件哈希，仅复制到新目录，不覆盖正在开发的源码。`rollback` 只切换到有审批证据的快照，不能把未评测恢复点变成稳定版，也不自动修改业务项目。切换后若中央工作区与该版本不同，`check/sync` 继续阻止；先在独立恢复目录核对，按授权整合回中央，再预览下发。项目自己改过的 Skill 仍按原同步规则保留冲突。

`before-anti-regression` 是修复前实际源码的 recovery-only 快照，并非历史稳定发布。不要误称它已经通过模型评测。

## 参考与取舍

来源固定为 [addyosmani/agent-skills@6ca0cd7](https://github.com/addyosmani/agent-skills/tree/6ca0cd7db39b41b1c37e26d335c507ee92382c6d)：

| 参考 | 采用 | 不直接照搬的原因 |
| --- | --- | --- |
| `constraint-driven-development` / `references/floor-guard.md` | 明确底线、检查校验器和测试被削弱、检查不能运行不算通过 | 不使用固定 80% 覆盖率，不用关键词扫描冒充语义判定，不新增全套工具依赖 |
| `evals/README.md` | 结构/路由/行为分层，execution 使用真实 fixture，独立评分、压力案例 | 中文否定词语误判仍如实报告，不将其 TF-IDF 阈值套到本库 |
| `evals/skill-impact.md` | 留下被评测否决的尝试及证据 | 原文件当前只有表头，不能宣称其已有量化效果证据 |
| `doubt-driven-development` | 分开原始产物、契约与作者结论，核实评审发现并限制无效循环 | 不采用每轮强制跨模型询问、每次重新授权，与本库持续授权和低摩擦目标冲突 |
| `code-simplification` | 简化前先理解存在原因，保存行为与项目约定 | 不以固定行数强制拆 PR，不把减少行数当作唯一收益 |

已存在类似能力时扩展现有协议，不再新增同义 Skill。
