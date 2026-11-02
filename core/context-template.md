---
id: project-context
title: 项目宪法模板
priority: critical
auto_load: true
version: 2.0
---

# 项目宪法

> 复制本文件到你的项目中，替换 `{{...}}` 占位符。
> 路径建议: `你的项目/.ai-skill/context.md` 或 `你的项目/docs/skills/_rules/PROJECT_CONTEXT.md`

## 项目概述

**项目名称**：{{项目名称}}
**一句话描述**：{{用一句话说清楚项目是什么、给谁用}}
**当前阶段**：{{开发中 / 已上线维护 / 重构中}}

## 技术栈

| 层 | 技术 |
|----|------|
| 语言 | {{Python 3.11 / TypeScript 5.x / Go 1.22 / ...}} |
| 前端 | {{React / Vue / PyQt6 / Flutter / 无}} |
| 后端 | {{FastAPI / Django / Express / Gin / 无}} |
| 数据库 | {{PostgreSQL / SQLite / MongoDB / 无}} |
| 部署 | {{Docker / Vercel / PyInstaller / 无}} |
| 包管理 | {{npm / pnpm / poetry / pip / go mod}} |
| 测试 | {{pytest / jest / vitest / go test}} |

## 目录结构

```
project-root/
├── {{目录1}}/    ← {{说明}}
├── {{目录2}}/    ← {{说明}}
├── {{目录3}}/    ← {{说明}}
└── ...
```

## 架构概览

{{描述系统的核心模块和数据流向，2-5 句话}}

## 关键约定

1. {{约定1，例: 所有 API 必须经过认证中间件}}
2. {{约定2，例: 前端不直接访问数据库}}
3. {{约定3，例: 配置文件不提交到 Git}}
4. {{约定4}}
5. {{约定5}}

## 运行方式

```bash
# 安装依赖
{{安装命令}}

# 启动开发服务器
{{启动命令}}

# 运行测试
{{测试命令}}

# 构建
{{构建命令}}
```
