---
name: flow
description: "用户明确要求工作流，或正在继续已启用工作流时，为项目创建、校验、启动或恢复多 Skill 工作流。排除普通 Skill 接入、一般多步骤任务、仅因任务较长而引入编排，以及根据目录存在自动接入。"
---

# /flow — 多 Skill 工作流

把跨多个 Skill、包含人工确认、等待外部数据或跨会话续跑的任务建模为版本化工作流。不要把整个长任务写成一个大 Skill。

## 入口兼容

- 支持自定义斜杠命令的工具：使用 `/flow ...`。
- Codex：使用 `$flow` 或自然语言。`/flow` 只有在工作流控制台中才是可执行命令；Codex 原生扩展入口不承诺任意斜杠命令。
- 工作流控制台默认地址为 `http://127.0.0.1:4319`，命令 API 为 `POST /api/workflows/commands`，请求体为 `{ "input": "..." }`。

## 标准命令

```text
/flow create <workflow-id> [--system <system-id>] [--name "名称"]
/flow validate <workflow-id>
/flow sync
/flow start <workflow-id> [--参数 "值"] [--idempotency-key <key>]
/flow status [run-id]
/flow pause <run-id>
/flow resume <run-id>
/flow cancel <run-id>
```

用户只输入 `/flow` 或要求“创建工作流”但没有 ID 时，一次只追问一个关键缺口；不要自行生成不可识别的正式 ID。

## 定义位置

### 项目工作流模式

普通 Skill 接入不询问工作流。首次明确请求接入工作流时，复用用户已给出的选择；补齐必要的系统 ID 与能力模式，再用初始化器的显式工作流参数写入 `.ai-skill/project/workflow-integration.json`。默认采用 `flow-lite`，更高模式须有相应证据；已有选择保持不变：

- `skill-only`：只加载 Skill、沉淀知识和参与治理，不加载或路由工作流。
- `flow-lite`：支持定义、Run、状态、审批和人工交付；不声称具备真实多 Agent 派发。
- `flow-standard`：在有真实 PM/Worker、dispatch、callback、验收和集成证据时使用。
- `flow-automated`：仅在 Standard 稳定后启用，额外要求租约、重试、死信和自动恢复证据。

显式首次接入命令（先通过 `ai-skill-bootstrap` 解析实际框架绝对路径）：

```powershell
python -X utf8 -B "<ai-skill-root>/scripts/init-project.py" --path "<project>" --ide codex --workflow-integration enabled --workflow-system-id <system-id> --workflow-mode flow-lite
```

首次接入时不覆盖已有策略；已有项目改变选择时，按用户明确的新决定更新其策略，保留其他字段和已有工作流数据。

模式不会因为发现工作流目录而自动启用，也不会把 `succeeded` 当成验收或集成完成。

优先把业务工作流放在业务项目中：

```text
<项目>/.ai-skill/workflows/<workflow-id>.workflow.json
```

只有跨项目或属于控制平面自身的定义才放在：

```text
<工作流控制台>/config/workflows/<workflow-id>.workflow.json
```

`/flow sync` 扫描这两类来源，但项目来源必须先有：

```text
<项目>/.ai-skill/project/workflow-integration.json
```

只有 `enabled: true` 且 `system_id` 与工作流控制台登记 ID 一致时，才扫描项目定义并把工作流路由到该项目。策略缺失或 `enabled: false` 时仍可正常使用和沉淀 Skill，但不加入工作流系统。不得因发现 `.ai-skill/workflows/`、Skill 目录或治理注册记录而自动启用。项目可以选择性维护自己的定义，中央库不直接覆盖项目业务流程。

## 必须满足的契约

1. Definition 与 Run 分离；Run 必须钉住启动时的 definition version。
2. `start` 只创建 `intake` 草稿，不立即调用 Skill 或生成素材。
3. 每个输入和输出声明 `id`、`type`、`required` 和说明。
4. 步骤依赖必须无环；嵌套 workflow 深度不超过定义的 `maxDepth`，且全局上限为 8。
5. `write` 或 `destructive` 步骤必须设置 `approval: before_step` 和稳定 `idempotencyKey`。
6. 等待输入、等待审批、暂停、失败和取消必须是显式状态，不能记作成功。
7. Skill 步骤必须把 Definition 声明的输出契约传给执行器，并校验全部必填输出；返回顶层或 `outputs` 内 `status=failed` 时，步骤和 Run 必须失败，不能因收到结构化对象而记作成功。
8. 外部业务对象使用稳定引用；新一轮迭代新增版本，不覆盖历史产物和指标。
9. 工作流负责状态、依赖、重试和审批；Skill 只负责单阶段业务动作。

## 状态模型

```text
intake -> ready -> running
                  -> waiting_input / waiting_approval / paused
                  -> succeeded / failed / cancelled
```

暂停时记录原状态，恢复后回到原状态。终态不可暂停或恢复。

## 交付证据模型

工作流执行完成后仍必须分开记录：

```text
执行 succeeded → delivery（交付证据）→ acceptance（人工验收）→ integrated（进入共享基线）
```

没有交付记录不能验收；没有 `accepted` 不能集成。没有真实传输或回调回执时，只能记录本地证据，不能宣称跨任务已送达。

后续步骤只有在其声明依赖的验收或集成事实满足时才可解锁；`succeeded`、交付、验收与集成必须分别记录。仅改变模式标签不建立真实派发、回调或自动恢复能力。

## 执行方式

1. 读取目标项目的 `AGENTS.md`、`.ai-skill/project/zones.md` 和现有 workflow 定义。
2. 读取 `.ai-skill/project/workflow-integration.json`；缺失时先确认是否加入工作流，关闭时停止创建或路由项目工作流。
3. 创建或修改定义前列出输入、输出、步骤依赖、副作用、审批点、检查点和完成证据。
4. 运行 `/flow validate <id>`；失败时只修复对应定义，不绕过校验。
5. 运行 `/flow sync`，确认同步的 ID、版本和目标系统。
6. 运行 `/flow start ...` 后报告 run ID、定义版本、缺失输入和当前 `intake` 状态。
7. 长任务每个有副作用的步骤执行前重新检查审批和幂等键，完成后持久化检查点。

自然语言“开始闲鱼上架工作流，产品是选品翻倍课程”必须与 `/flow start xianyu-listing --product "选品翻倍课程"` 进入同一个 command service，并生成同一种 Run 记录。

## 输出契约

报告工作流 ID、定义版本、Run ID（实际创建后）、当前状态、缺失输入与交付证据；分别说明执行、交付、验收和集成，不推断跨任务送达。
