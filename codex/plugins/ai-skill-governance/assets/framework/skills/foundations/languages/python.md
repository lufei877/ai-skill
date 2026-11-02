---
id: lang-python
description: "编写、修改或审查 Python 代码时使用，检查类型、资源和异常边界并遵循项目现有工具。排除仅提到 Python 的资讯和不涉及代码的任务。"
title: Python 语言规范
category: foundations
trigger: python,py,pip,poetry,django,flask,fastapi,pytest
priority: high
auto_load: false
version: 1.0
---

# Python 语言规范

## 什么时候读
编写或修改 Python 代码时自动加载。

## 编码风格
1. 遵循 PEP 8，行宽 88（兼容 black）
2. 使用 type hints（Python 3.10+ 语法：`list[str]` 而非 `List[str]`）
3. docstring 用 Google 风格
4. import 顺序：stdlib → third-party → local，各组之间空一行
5. 使用 f-string 而非 `.format()` 或 `%`

## 安全规范
1. SQL 用参数化查询，禁止 f-string 拼 SQL
2. 用 `secrets` 模块生成 token，不用 `random`
3. 文件路径用 `pathlib.Path`，防止路径注入
4. 反序列化禁用 `pickle.loads` 处理不信任数据，用 JSON
5. 密钥走 `os.environ` 或 `.env`，不硬编码

## 测试规范
1. 测试文件 `test_*.py`，测试函数 `test_<行为>_<条件>_<预期>`
2. 使用项目已有测试工具，按关键行为和风险选择覆盖范围，不用统一覆盖率替代验证质量
3. 跨测试共享的 fixture 放 `conftest.py`；单次使用的数据保持就近、自包含
4. mock 外部依赖（API、DB），不 mock 被测代码本身

## 常见坑
- 可变默认参数：`def f(items=[])` → 用 `def f(items=None)`
- 迭代中修改容器 → 先 `list()` 复制
- `is` vs `==`：对象身份 vs 值相等
- `datetime.now()` 无时区 → 用 `datetime.now(timezone.utc)`

## 正例
```python
from pathlib import Path
from datetime import datetime, timezone

def process_users(
    db: Database,
    *,
    active_only: bool = True,
    limit: int = 100,
) -> list[dict]:
    """获取并处理用户列表。"""
    query = "SELECT * FROM users WHERE active = %s LIMIT %s"
    rows = db.execute(query, (active_only, limit))
    return [{"id": r.id, "name": r.name} for r in rows]
```

## 反例
```python
def process_users(db, active_only=True, limit=100):
    rows = db.execute(f"SELECT * FROM users WHERE active = {active_only} LIMIT {limit}")
    result = []
    for r in rows:
        result.append({"id": r.id, "name": r.name})
    return result
```

## 输出契约

交付符合项目 Python 约定的改动或具体审查发现；说明必要的验证结果及仍未覆盖的行为。
