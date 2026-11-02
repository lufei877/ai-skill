---
id: zones
title: 文件分区规则（通用模板）
priority: critical
auto_load: true
version: 2.0
---

# 文件分区规则

> 将项目文件分为三个区域，AI 对不同区域有不同的操作权限。
> 本文件为通用模板，项目清单优先读取 `.ai-skill/project/zones.md`；已有 `ZONE_RULES.md` 可继续引用。

## 冻结区（Frozen）

AI **绝对不能** 修改的文件。需要修改时必须声明 `[UNFREEZE: 文件路径]` + 原因，等用户确认。

**可选择冻结的文件示例（不自动构成冻结清单）**：
- 核心安全模块（认证、加密、权限）
- 数据库 migration 文件（已执行的）
- CI/CD 配置（.github/workflows, Jenkinsfile）
- 锁文件（package-lock.json, poetry.lock）
- 环境配置模板（.env.example）

## 受控区（Controlled）

AI 可以修改，但每次改动必须说明原因 + 影响范围。

**常见受控文件**：
- 数据库模型/Schema 定义
- API 路由定义
- 全局配置文件
- 公共组件库

## 活跃区（Active）

AI 可自由修改，遵守 constraints.md 即可。

**常见活跃文件**：
- 业务逻辑代码
- UI 组件
- 测试文件
- 文档

## 分区判断规则

1. 未列出的文件默认属于 **活跃区**
2. 冻结区文件清单必须完整、精确
3. 新建文件自动属于活跃区
4. 清单未明确时先查项目约定；未列出的文件不因下面的示例自动冻结，具体高风险操作按 RULES.md 的授权边界判断。
