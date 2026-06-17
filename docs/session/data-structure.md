# 会话持久化数据结构

> 最后更新：2026-06-17

## SessionRecord

```ts
type SessionRecord = {
  id: string
  title: string
  cwd: string
  model: string
  createdAt: number
  updatedAt: number
  messageCount: number
}
```

## SessionEvent

```ts
type SessionEvent =
  | { type: 'message'; message: ChatMessage }
  | { type: 'runtime_event'; event: RuntimeEvent }
  | { type: 'permission_decision'; requestId: string; decision: PermissionDecision }
  | { type: 'task_state'; task: TaskState }
  | { type: 'metadata'; patch: Partial<SessionRecord> }
```

## SessionStore

```ts
type SessionStore = {
  create(input: CreateSessionInput): Promise<SessionRecord>
  append(sessionId: string, event: SessionEvent): Promise<void>
  load(sessionId: string): Promise<LoadedSession>
  list(filter: SessionFilter): Promise<SessionRecord[]>
}
```

## LoadedSession

```ts
type LoadedSession = {
  record: SessionRecord
  events: SessionEvent[]
  messages: ChatMessage[]
  tasks: TaskState[]
}
```

