# Skill 模型评测协议

本库当前提供结构、契约和词语冒烟检查。它们不证明真实模型的触发准确率、产物质量或成本改善。

## 对照方法

使用 `evals/model-task-cases.json` 中的代表任务。每个案例在隔离的同一项目快照中运行三种条件：不加载本库、调整前版本、当前版本。固定模型实际 ID、推理配置、工具、测试数据和上下文；只改变库指令。没有调整前快照时明确缺少该条件，不能重造一个更差的基线。

基础任务使用 core 组。`without-library` 条件不要求选中特定 Skill，但仍检查最终行为。预先准备案例中引用的按钮、代码变更、产品事实和已确认计划，未准备真实输入时不执行空壳测试。

每次记录：`case_id`、`variant`、`model`、`reasoning`、唯一 `run_id`、`selected_skills`、`outcome_passed`、`unnecessary_questions`、`unauthorized_actions`、`elapsed_ms`、可取得的 `input_tokens`，以及任务记录或回放文件 `evidence_path`。复杂度案例可额外记录实际观察到的 `unnecessary_dependencies`、`unnecessary_abstractions`、`unauthorized_simplifications`、`verification_gaps` 和 `changed_lines`；缺少观测时保持未知，不补零。行为是否合格应由人工或独立评审对照预先声明的 acceptance 判断，不能只让执行模型自评。

先完成代表任务的小批验证，再根据差异重复有争议案例。若结果波动显著，增加重复次数并报告分布。不要因单次成功就调整生产默认模型。

## 验证记录

记录 JSON 的顶层为 `{"runs": [...]}`。路径相对结果 JSON 所在目录；每条 evidence_path 指向已存在的本地任务记录。运行：

```powershell
python scripts/skill_factory.py model-eval --cases evals/model-task-cases.json --results <结果文件.json>
```

命令校验记录完整性并按模型、推理配置和条件汇总，不调用模型、不产生任务记录、不验证人工评分真伪。报告缺失案例和路由匹配数；未经实际运行的结果不能填成成功。耗时、token、修改行数和复杂度指标仅汇总实际给出的观测值，不能推算或补零；修改行数只用于观察范围，不能代替任务通过率和保护边界。

## 当前状态

21 个代表任务已定义，其中包含标准库/现有能力复用、提前抽象、受保护校验和复杂度专项路由案例；尚未运行三条件对照，没有最新模型性能提升结论。最新模型 ID 和参数在正式运行时从当前可用能力确认，不写死在 Skill 正文里。

9 个营销 Skill 的 54 条词语冒烟用例中，52 条通过，2 条含否定表达的中文近邻请求仍被词语算法误判：产品列表组件“不做营销分析”和报价页面“不做套餐调整”。保留原本的 no-trigger 期望，不通过改标签或移除案例制造全绿；这两个请求也进入真实模型任务集。冒烟命令在这些文件上返回非零，代表已知的词语算法局限，不能当作实际模型失败或成功。
