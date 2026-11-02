---
name: security-basics
description: "实现或审查认证、权限、输入信任边界与敏感信息处理时使用。排除仅提到 token、key 的非安全工作，不因术语命中扩大审查范围。"
---

# 基础安全规范

## 什么时候读
涉及认证、授权、数据校验、敏感数据处理时加载。

## 规则
1. 密钥/密码/token 走环境变量，绝不硬编码或提交到 git
2. 用户输入必须校验和清洗——永远不信任前端数据
3. SQL 使用参数化查询，禁止字符串拼接
4. HTML 输出转义，防止 XSS
5. 文件上传校验类型和大小，存储路径不可由用户控制
6. API 接口必须有认证和授权检查
7. 敏感操作加速率限制
8. 日志中不记录密码、token 等敏感信息

## 正例
```python
# 参数化查询
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# 环境变量
api_key = os.environ["API_KEY"]
```

## 反例
```python
# SQL 注入
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# 硬编码密钥
API_KEY = "sk-1234567890abcdef"
```

## 关联 skill
- error-handling

## 输出契约

给出具体信任边界、发现或修复及验证依据；无法核验的安全结论明确保留未知。
