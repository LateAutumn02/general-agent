# 权限审批数据结构

> 最后更新：2026-06-17

## PermissionMode

```ts
type PermissionMode = 'default' | 'acceptEdits' | 'plan' | 'bypassPermissions'
```

## PermissionRequest

```ts
type PermissionRequest = {
  id: string
  toolName: string
  preview: PermissionPreview
  suggestions: PermissionRuleSuggestion[]
  createdAt: number
}
```

## PermissionDecision

```ts
type PermissionDecision =
  | { type: 'allow'; remember: false }
  | { type: 'allow'; remember: true; rule: PermissionRule }
  | { type: 'deny'; reason?: string }
```

## PermissionRule

```ts
type PermissionRule = {
  id: string
  scope: 'session' | 'project' | 'user'
  toolName: string
  pattern: string
  behavior: 'allow' | 'deny'
}
```

## PermissionPreview

```ts
type PermissionPreview =
  | { type: 'command'; command: string; cwd: string }
  | { type: 'file_edit'; filePath: string; diff: string }
  | { type: 'file_read'; filePath: string }
  | { type: 'generic'; text: string }
```

