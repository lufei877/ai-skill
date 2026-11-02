# 来源与维护

## Agent 体检来源

- 上游：[tw93/Waza Health](https://github.com/tw93/Waza/tree/8b2c3560ba0b174a5c984b75e4417d5c2e7453f8/skills/health)
- 固定提交：`8b2c3560ba0b174a5c984b75e4417d5c2e7453f8`，本地适配日期：2026-10-11。
- 保留内容：按层体检、摘要优先、实际证据优先、区分全局/项目问题及运行验证层次。许可随包保存在 [../LICENSE](../LICENSE)。
- 本地实现：采集器使用 Python 3.11+ 标准库重写，不依赖 Bash、awk 或动态下载。修正实测暴露的 TOML 路径、委托判定、Skill 扫描覆盖与编码问题；相关回归位于中央 `tests/test_health.py`。
- Waza 适配范围：Codex/Claude 的静态配置和指令、MCP 可执行路径、候选 Skill 树、验证入口清单；深入核实由 Agent 按当前证据执行。没有移植整套 Waza、历史采集器、自动并行检查器或上游 CLI，也不声称与上游功能完全等价。

## 软件审计来源

- 来源：用户提供的 `屎山清除skill.zip`，包内目录 `Fuck_My_Shit_Mountain-main/fuck-my-shit-mountain/`；本地适配日期：2026-10-12。
- 原始压缩包 SHA256：`607a1070832ec60d6e54c7e465d659f8d5e8fe94a0d6ce145f38a3d87855e284`。未核实上游仓库和提交，以该哈希固定本次参考，不自动追踪同名仓库或 main。
- 原件仅作为只读参考，采用其 SKILL、prompts、rubrics 与报告模板中的安全/稳定/维护性/测试真实性维度、可达路径、置信度与修复验证要求。根 MIT 许可原文见 [../CODE-AUDIT-LICENSE](../CODE-AUDIT-LICENSE)。
- 本地重写为按需参考：软件地图与覆盖、安全检查、维护性检查和报告契约。沿用现有 health 入口；普通全面体检覆盖三条线，范围明确时收窄。标准库 `collect_software.py` 仅提供有预算和排除记录的文件清单、规模及逐字节重复候选；源码语义、安全与维护成本仍由 Agent 复核。回归位于中央 `tests/test_health_software.py`。
- 未采用强制三轮提问、逐文件逐函数穷尽保证、默认多维评分、按行数定罪、把 TODO/mock/DI/所有 fallback 视为缺陷等规则；没有移植巨型 HTML 模板、下载/安装指令或全仓重写要求。

## 维护与交付

- 维护者：ai-skill。出现可复现误报、平台配置变化或准备稳定发布时复核本包；上游升级需选定新提交、检查差异并重跑相关 fixture，不自动追踪 main。
- 压缩包来源升级需记录新内容哈希、核对许可和适配差异。新增维度须能对应项目适用性、具体证据和最小修法；不能只扩关键词表、打分公式或安全保证。
- 入库与发布：权威源是 `codex/skills/health`，编译到 `.agents/skills/health` 和本地治理插件。中央源码接入、确定性测试、模型行为评测、稳定发布和跨项目安装分别记录，不能相互替代。
