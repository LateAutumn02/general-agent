# 沙箱安全数据结构

> 最后更新：2026-06-17

## SandboxPolicy

```ts
type SandboxPolicy = {
  cwd: string
  allowedDirs: string[]
  denyCommands: string[]
  allowReadOnlyCommands: boolean
}
```

## SandboxDecision

```ts
type SandboxDecision =
  | { type: 'allow' }
  | { type: 'deny'; reason: string }
  | { type: 'ask'; reason: string }
```

## PathAccessRequest

```ts
type PathAccessRequest = {
  operation: 'read' | 'write' | 'delete'
  path: string
  cwd: string
}
```

