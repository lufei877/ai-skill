---
id: pitfalls
description: "定位已记录故障时按根因或错误特征查阅踩坑记录，优先项目知识并核对适用环境。排除仅因出现问题、失败等泛词就加载整份历史知识。"
title: 踩坑记录
category: knowledge
trigger: 坑,bug,问题,报错,error,crash,失败,fail
priority: high
auto_load: false
self_evolve: true
version: 1.0
---

# 踩坑记录

> AI 可以追加新条目；新证据可补充 active 条目，失效规则通过 `superseded_by` 显式替代，不直接删除历史。
> 每条记录帮助后续 AI 避免重蹈覆辙。

## 追加规则
- 格式：`### PIT-{编号}: {标题}`
- 必须包含：现象、原因、解决方案、日期
- 具有通用性的问题才记录（项目特有的记到项目目录）
- 编号递增，不复用

---

### PIT-001: Python 字典在迭代中修改导致 RuntimeError

**现象**：遍历 dict 时删除元素，抛出 `RuntimeError: dictionary changed size during iteration`
**原因**：Python 3 不允许在迭代中修改字典大小
**解决**：先 `list(dict.keys())` 复制 key 列表，再遍历删除；或用字典推导式创建新字典
**日期**：2025-01-01

### PIT-002: Node.js ESM/CJS 混用导致 import 失败

**现象**：`ERR_REQUIRE_ESM` 或 `SyntaxError: Cannot use import statement outside a module`
**原因**：package.json 未设置 `"type": "module"` 或依赖包只提供 ESM
**解决**：统一使用 ESM（加 `"type": "module"`），或用 `import()` 动态导入 ESM 包
**日期**：2025-01-01

### PIT-003: Git rebase 后 force push 覆盖同事代码

**现象**：`git push --force` 后队友的 commit 消失
**原因**：force push 用本地历史替换远程历史
**解决**：用 `--force-with-lease` 代替 `--force`，会检查远程是否有新提交
**日期**：2025-01-01

### PIT-004: PowerShell 语句级 foreach 不能直接续接管道

**现象**：`foreach (...) { ... } | Format-Table` 报 `An empty pipe element is not allowed`
**原因**：Windows PowerShell 的语句级 `foreach` 不是可直接续接管道的表达式
**解决**：先用 `$rows = foreach (...) { ... }` 收集输出，再执行 `$rows | Format-Table`
**范围**：cross-project
**证据**：在本次 Windows PowerShell 审计命令中复现，并用分步收集方式验证通过
**状态**：active
**日期**：2026-08-05

### PIT-005: Windows Python 校验中文 UTF-8 文件时默认编码不一致

**现象**：有效 UTF-8 的中文 `SKILL.md` 被 Python 校验脚本按 GBK 读取，出现解码错误或误判
**原因**：Windows 上未显式指定编码的 `open()` 会使用系统默认代码页，而仓库文本统一为 UTF-8
**解决**：校验器读取文本时显式使用 `encoding="utf-8"`；无法立即修改第三方校验器时，用 `PYTHONUTF8=1` 运行。PowerShell 5.1 将 JSON 管道给原生进程时还可能加入 UTF-8 BOM，stdin JSON 入口应只剥离开头的 `\ufeff` 或使用 `utf-8-sig`
**范围**：cross-project
**证据**：Codex 原生 skill 全量校验先复现默认编码失败，启用 Python UTF-8 模式后 26 个 skill 全部通过；2026-08-07 真实会话归档复现 PowerShell 管道 BOM，脚本兼容并增加回归测试后写入成功
**状态**：active
**日期**：2026-08-05

**补充证据（2026-08-17，2026-09-09 从 PIT-004 纠正归类）**：`skill-creator` 的 `generate_openai_yaml.py` 在 Windows 使用未指定编码的 `Path.write_text()`，中文界面字段被写成 GBK，中央 `compile-targets.py` 按 UTF-8 读取时稳定复现 `UnicodeDecodeError`。为生成器与初始化器的文本写入显式增加 `encoding="utf-8"` 后，含中文的 `agents/openai.yaml` 可被严格 UTF-8 读取，中央 Skill 编译恢复通过。

### PIT-006: Windows Python 不能把 npm cmd shim 当普通可执行文件启动

**现象**：Python `subprocess.run(["codex", ...])` 命中 npm shim 后返回 `WinError 5`，但 PowerShell 中可正常执行同一命令
**原因**：Windows npm CLI 实际入口是 `.cmd` shim，不是可由 `CreateProcess` 直接启动的原生可执行文件
**解决**：用 `shutil.which("codex.cmd")` 解析入口，并通过 `cmd.exe /d /c <shim> ...` 调用；非 Windows 保持直接执行
**范围**：cross-project
**证据**：本次插件安装脚本复现失败，改用 `.cmd` 解析后 marketplace 查询与插件安装均成功
**状态**：active
**日期**：2026-08-05

### PIT-007: Codex 仓库 marketplace 必须使用原生清单路径

**现象**：将 marketplace 清单放在 `codex/marketplace.json` 后，Codex CLI 无法发现该本地 marketplace
**原因**：Codex 期望 marketplace 清单位于 marketplace 根目录的 `.agents/plugins/marketplace.json`
**解决**：把清单放到 `codex/.agents/plugins/marketplace.json`，并以 `codex` 目录作为 marketplace 根目录安装
**范围**：cross-project
**证据**：根级清单未被 CLI 识别，迁移到原生路径后 `ai-skill-governance@ai-skill-local` 安装并启用
**状态**：active
**日期**：2026-08-05

### PIT-008: Windows Path.write_text 改写 AGENTS.md 的原有换行

**现象**：只在 `AGENTS.md` 追加托管区时，非托管内容的 LF 被整体改成 CRLF，Git diff 看似只有追加但文件字节发生变化
**原因**：Windows `Path.write_text()` 使用系统换行转换，无法保证已有文件的换行风格
**解决**：根据原文检测 LF/CRLF；用 `Path.open(..., newline="")` 写回，仅替换托管区并保持原有换行
**范围**：cross-project
**证据**：在两个真实项目下发时复现；新增回归测试后修复，知识文件和 AGENTS 非托管区逐字节校验通过
**状态**：active
**日期**：2026-08-06

## 输出契约

返回与当前故障相关的条目、适用前提和验证方式；无匹配时继续定位，不编造历史证据。
