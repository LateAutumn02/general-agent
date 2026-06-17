# 记忆系统数据结构

> 最后更新：2026-06-17

## MemoryScope

```ts
type MemoryScope = 'user' | 'project' | 'local'
```

## MemoryFile

```ts
type MemoryFile = {
  scope: MemoryScope
  path: string
  content: string
  loadedAt: number
}
```

## MemoryState

```ts
type MemoryState = {
  enabled: boolean
  files: MemoryFile[]
  promptText: string
}
```

## MemoryStore

```ts
type MemoryStore = {
  load(cwd: string): Promise<MemoryState>
  refresh(cwd: string): Promise<MemoryState>
  write(scope: MemoryScope, patch: string): Promise<void>
}
```

