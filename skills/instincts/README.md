# Instincts — AI 行为本能层

> 灵感来源：everything-claude-code 的 homunculus/instincts 系统。
> Instinct 是介于"规则"和"skill"之间的行为模式，用于编码 AI 的持久化直觉。

## 什么是 Instinct

- **Rule**（规则）= "不可以做什么" — 硬性约束
- **Skill**（技能）= "怎么做某件事" — 领域知识
- **Instinct**（本能）= "遇到某种情况时，自动这样做" — 行为模式

## 格式

每个 instinct 是一个 YAML 文件，结构：

```yaml
id: instinct-id
name: 行为名称
trigger: 什么情况下触发
action: 触发后做什么
evidence: 为什么这样做（经验来源）
examples:
  - 示例场景1
  - 示例场景2
```

## 当前 Instincts

| ID | 名称 | 核心行为 |
|----|------|---------|
| fix-and-continue | 小问题直接修 | 遇到 import/类型/路径等小障碍直接修复，不暂停 |
| search-before-code | 先搜再改 | 动手前确认上下文和可复用实现 |
| verify-before-commit | 提交前验证 | 完成前跑测试 + 清理 debug 代码 |
| ask-before-big-change | 高风险改动前确认 | 仅冻结区/数据库/删模块时暂停 |
| match-existing-style | 匹配已有风格 | 保持代码风格一致 |
| learn-from-mistakes | 从错误中学习 | 通用问题记录到 knowledge |

## 加载方式

Instincts 的核心行为已内联到 RULES.md 第四节，AI 读完入口文件即自动生效。
YAML 文件保留完整的 trigger/action/evidence 细节，作为参考定义，
不需要每次会话逐文件读取。
