---
name: lang-go
description: "编写、修改或审查 Go 代码时使用，检查错误传播、资源释放和并发安全。排除仅出现 go 单词的非 Go 编码任务。"
---

# Go 语言规范

## 什么时候读
编写或修改 Go 代码时自动加载。

## 编码风格
1. 遵循 `gofmt` / `goimports` 格式化
2. 错误处理：`if err != nil` 逐层传播，不忽略错误
3. 包名小写单词，不用下划线或驼峰
4. 接口小而精，单方法接口优先（`io.Reader` 风格）
5. 避免 `init()`，显式初始化

## 安全规范
1. SQL 用 `db.Query("... WHERE id = $1", id)` 参数化
2. HTTP handler 设超时：`http.Server{ReadTimeout, WriteTimeout}`
3. 并发操作用 `sync.Mutex` 或 channel 保护共享状态
4. 不信任外部输入，校验后再用

## 测试规范
1. 测试文件 `*_test.go`，表驱动测试（table-driven）
2. 用 `t.Run` 子测试，名字描述场景
3. benchmark 用 `*testing.B`
4. 测试 helper 调用 `t.Helper()`

## 常见坑
- goroutine 泄漏：确保 channel 被关闭或 context 取消
- `defer` 在循环内 → 资源到函数结束才释放
- slice append 可能共享底层数组 → 需要时用 `copy`
- `nil` interface vs nil pointer → 类型断言前检查

## 正例
```go
func GetUser(ctx context.Context, db *sql.DB, id int64) (*User, error) {
    var u User
    err := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = $1", id).
        Scan(&u.ID, &u.Name)
    if err != nil {
        return nil, fmt.Errorf("get user %d: %w", id, err)
    }
    return &u, nil
}
```

## 输出契约

交付 Go 改动或审查发现，并报告错误路径、并发与资源释放相关的必要验证。
