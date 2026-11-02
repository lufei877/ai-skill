---
description: "用户要求从项目提炼可复用 Skill 时检查已有实现和证据并生成候选。排除普通代码阅读、未经验证的经验沉淀和自动发布中央规则。"
---

# /learn — 学习当前项目

## 流程

### 1. 扫描项目结构
- 读取目录结构、package.json / pyproject.toml / go.mod
- 识别技术栈、框架、工具链

### 2. 分析代码风格
- 采样 3-5 个核心文件
- 提取：缩进风格、命名约定、注释风格、导入顺序
- 自动识别结果写入 `.ai-skill/project/detected.md`
- 需要长期保留且无法静态推断的约定写入 `.ai-skill/project/context.md`

### 3. 分析 git 历史（如果可用）
- `git log --oneline -20` 看 commit 风格
- `git shortlog -s -n` 看主要贡献者
- 提取 commit message 约定

### 4. 识别项目约定
- 检查 linter 配置（.eslintrc, pyproject.toml [tool.ruff], .golangci.yml）
- 检查 CI 配置（.github/workflows）
- 检查已有的 README、CONTRIBUTING

### 5. 生成项目知识
- 将静态识别结果写入 `.ai-skill/project/detected.md`
- 将明确偏好和决定分别路由到 `preferences.md`、`decisions.md`
- 如果发现不同触发目标的特殊工作流 → 创建 `.agents/skills/<name>/SKILL.md`
- 更新 `.ai-skill/project/zones.md` 的文件分区建议
- 不记录未验证推测、密钥或原始会话全文

### 6. 报告
输出学习摘要，让用户确认是否准确。

## 输出契约

给出适用范围、触发条件、输出与来源证据；已有同类 Skill 时优先建议补充，发布遵守授权边界。
