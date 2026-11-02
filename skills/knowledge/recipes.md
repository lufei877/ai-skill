---
id: recipes
description: "需要复用已验证的接入、知识记录或创建项目 Skill 的流程时查阅配方，并优先专项 Skill。排除一般怎么做问题与尚未验证的新流程设计。"
title: 常用操作配方
category: knowledge
trigger: 怎么做,how to,配方,recipe,步骤,操作,流程
priority: medium
auto_load: false
self_evolve: true
version: 1.0
---

# 常用操作配方

> 已验证知识先记录到项目；中央更新须有授权。补充 active 条目，失效流程用 `superseded_by` 显式替代。
> 标准化的操作步骤，避免每次重新摸索。

## 追加规则
- 格式：`### RECIPE-{编号}: {标题}`
- 必须包含：场景、步骤、注意事项
- 编号递增，不复用

---

### RECIPE-001: 新项目接入 ai-skill

**场景**：将 ai-skill 框架接入一个新项目
**步骤**：
1. 运行 `python <ai-skill根目录>\scripts\init-project.py --path <项目路径> --ide codex`
2. 检查 `.ai-skill/project/detected.md` 的自动技术栈与命令识别
3. 按需补充 `.ai-skill/project/context.md`、`zones.md`、`preferences.md` 和 `decisions.md`
4. 确认 `.agents/skills/` 已部署原生 Codex skills
5. 重复运行一次，确认已有 `AGENTS.md` 和项目知识未被覆盖
**注意**：当前会话在初始化后要显式读取新入口；新 Codex 会话会自动发现

### RECIPE-002: 记录一个新的踩坑

**场景**：开发中遇到了一个有通用价值的问题并解决
**步骤**：
1. 判断是通用问题还是项目特有问题
2. 项目特有 → 更新 `项目/.ai-skill/project/knowledge/pitfalls.md`
3. 单项目完整证据可进入中央候选，多项目复现提升置信度；用户批准后才写入中央权威源
4. 填写 scope、evidence、verified_at、status、现象、根因、修复和预防
5. 已有近似条目优先补充；规则变化时用 `superseded_by` 替代
**注意**：没有复现、根因和修复验证时不记录

### RECIPE-003: 创建项目特有 Skill

**场景**：项目有特殊的规范需要 AI 遵守
**步骤**：
1. 在项目 `.agents/skills/<skill-name>/SKILL.md` 创建 Codex 原生 skill
2. frontmatter 只写 `name` 和触发清晰的 `description`
3. 详细项目事实放 `.ai-skill/project/`，避免 skill 与知识库维护双份事实
4. 用 skill-creator 的 `quick_validate.py` 校验
**注意**：优先扩展已有 skill；不同触发目标才拆新 skill

## 输出契约

给出适用配方、当前场景所需调整和已完成步骤的证据；新知识按项目进化协议另行记录。
