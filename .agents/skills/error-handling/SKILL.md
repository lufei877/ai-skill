---
name: error-handling
description: "设计或修复异常处理、重试、日志与资源清理路径时使用。排除只包含 error 字样的业务文案和无需改动错误边界的问题。"
---

# 错误处理规范

## 什么时候读
涉及异常捕获、错误处理、日志记录，或为交付给用户的软件设计错误兜底与诊断导出时加载。

## 规则
1. 禁止空 catch/except — 至少记录日志
2. 捕获具体异常类型，不要裸 `except Exception`（除非是最外层兜底）
3. 日志必须包含足够上下文：who（用户/请求ID）, what（操作）, why（错误信息）
4. 不要用异常控制正常流程（异常是异常，不是 if-else）
5. 面向用户的错误信息不暴露内部细节（堆栈、SQL、文件路径）
6. 异步操作的异常不能被静默吞掉
7. 交付给用户运行的软件（桌面端、客户端、常驻服务）在进程入口设置全局兜底：捕获未处理异常和未处理的 Promise 拒绝（如 Node/Electron 的 `uncaughtException`、`unhandledRejection`，渲染进程崩溃，Python 的 `sys.excepthook`），写入带版本号和时间的本地日志。兜底只负责记录和安全退出或提示，不代替业务层的具体处理
8. 交付给用户运行的软件提供一键导出诊断包：近期日志、软件版本与构建号、操作系统信息、脱敏后的关键配置和状态。导出前过滤 Cookie、token、密码、密钥和账号凭据，并用测试确认诊断包中不含这些内容。诊断包只保存在本地，由用户自己决定发给谁；需要自动上传时另行设计并获得授权

## 正例
```python
try:
    result = payment_service.charge(user_id, amount)
except PaymentDeclinedError as e:
    logger.warning(f"Payment declined for user={user_id}: {e}")
    raise HTTPException(400, "Payment was declined")
except Exception as e:
    logger.exception(f"Unexpected payment error for user={user_id}")
    raise HTTPException(500, "Internal error")
```

## 反例
```python
try:
    do_something()
except:
    pass
```

## 关联 skill
- security-basics

## 输出契约

给出异常如何传播、处理或记录的具体改动与验证；指出重试与不可恢复失败的边界。
