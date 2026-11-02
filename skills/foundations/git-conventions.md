---
id: git-conventions
description: "准备提交、整理分支、合并或变基时使用，检查改动范围、提交信息与协作安全。排除一般代码编辑和未要求 Git 操作的解释任务。"
title: Git 提交规范
category: foundations
trigger: git,commit,提交,分支,branch,merge,rebase
priority: high
auto_load: false
version: 1.1
---

# Git 提交规范

## 什么时候读
涉及 git 操作（提交、合并、分支管理）时加载。

## 规则
1. commit message 使用 Conventional Commits 格式: `type(scope): description`
2. type 包括: feat, fix, docs, style, refactor, test, chore, perf, ci
3. 一次 commit 只做一件事——不要把不相关的改动混在一起
4. 不 force push 到 main/master，除非用户明确要求
5. 先 pull 再 push，避免冲突覆盖他人代码
6. 不跳过 hooks（--no-verify），除非用户明确要求
7. 单次提交超过 30 个文件或 2000 行（不含自动生成及 lock 文件）必须拆分，或在提交正文说明不可拆原因。
8. 禁止 sync snapshot 类整体快照提交；一次提交只承载可独立验证的一件事。
9. 分支命名和合入方式按项目约定（如工单要求的前缀、经 PR 合入 main）；项目没有约定时使用 `feat/`、`fix/`、`perf/`、`chore/` 前缀。
10. 提交前运行暂存区敏感信息检查；项目提供了 hook 目录时，新 clone 后按项目说明启用（如 `git config core.hooksPath <目录>`）。不得因已创建 CI 文件就宣称检查通过或分支保护生效。

## 正例
```
feat(auth): add OAuth2 login with Google
fix(cart): prevent negative quantity on item update
docs: update API endpoint documentation
```

## 反例
```
update code
fix bug
changes
WIP
```

## 关联 skill
- quality-review

## 输出契约

报告实际执行的 Git 动作、相关提交或分支与验证结果；未执行的推送、合并和发布不得标为完成。
