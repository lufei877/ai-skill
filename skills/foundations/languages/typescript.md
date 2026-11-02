---
id: lang-typescript
description: "编写、修改或审查 TypeScript/JavaScript 代码时使用，检查类型和运行时边界，保留项目模块与框架约定。排除仅提到 React 或 Node 的非编码问题。"
title: TypeScript 语言规范
category: foundations
trigger: typescript,ts,tsx,javascript,js,jsx,node,react,vue,next,nuxt,npm,pnpm,bun
priority: high
auto_load: false
version: 1.0
---

# TypeScript 语言规范

## 什么时候读
编写或修改 TypeScript/JavaScript 代码时自动加载。

## 编码风格
1. 优先 TypeScript，避免 `any`（用 `unknown` 然后 narrow）
2. 用 `interface` 定义对象形状，`type` 用于联合/交叉/工具类型
3. 遵循现有导出风格与框架入口契约；没有约定时优先 named export
4. 优先 `async/await`；保留已有清晰的 Promise 链，不为风格做无关重写
5. 使用 optional chaining (`?.`) 和 nullish coalescing (`??`)

## 安全规范
1. 外部输入在信任边界校验，优先项目已有方案；只有确有需要且无现有能力时再选 `zod` 等库
2. 不执行不可信代码，不注入未清洗 HTML；遵循框架的安全渲染接口
3. API key 走环境变量 `process.env.XXX`，不硬编码
4. 使用 `DOMPurify` 清洗用户生成的 HTML
5. Cookie 设置 `HttpOnly`, `Secure`, `SameSite`

## 测试规范
1. 测试文件 `*.test.ts` 或 `*.spec.ts`，紧挨源文件或在 `__tests__/`
2. 用 `describe/it` 结构，测试名描述行为
3. 组件测试用 `@testing-library`，避免测实现细节
4. 单元测试使用可控 stub/fixture；集成测试可访问获准的隔离服务，不能用 mock 通过代替真实集成结论

## 常见坑
- ESM vs CJS：保持项目现有模块系统，不因语言规范自动迁移
- `===` vs `==`：始终用严格等于
- 独立任务需要收集部分失败结果时用 `Promise.allSettled`；要求整体失败的任务可用 `Promise.all`
- React 闭包陷阱 → useRef 或 useCallback 依赖数组
- `JSON.parse` 无 try-catch → 总可能抛错

## 正例
```typescript
interface User {
  id: string;
  name: string;
  email: string;
}

async function fetchUsers(
  limit: number,
  parseUsers: (data: unknown) => User[], // 调用方传入项目已有的运行时验证器
): Promise<User[]> {
  const response = await fetch(`/api/users?limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch users: ${response.status}`);
  }
  const data: unknown = await response.json();
  return parseUsers(data);
}
```

## 反例
```typescript
// any, no error handling, template string injection
async function fetchUsers(limit: any) {
  const response = await fetch("/api/users?limit=" + limit);
  return response.json();
}
```

## 输出契约

交付符合项目框架与模块约定的改动或审查发现；涉及外部输入时说明实际验证边界，类型断言不作为运行时校验证据。
