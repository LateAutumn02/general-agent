# 后台任务数据结构

> 最后更新：2026-06-17

## TaskState

```ts
type TaskState = {
  id: string
  type: 'agent' | 'shell'
  status: TaskStatus
  description: string
  activity?: string
  messages: ChatMessage[]
  output?: TaskOutputRef
  createdAt: number
  updatedAt: number
}
```

## TaskStatus

```ts
type TaskStatus = 'pending' | 'running' | 'awaiting_input' | 'completed' | 'failed' | 'cancelled'
```

## ShellTaskState

```ts
type ShellTaskState = TaskState & {
  type: 'shell'
  command: string
  cwd: string
  exitCode?: number
  backgrounded: boolean
}
```

## TaskRegistry

```ts
type TaskRegistry = {
  create(input: CreateTaskInput): TaskState
  update(id: string, patch: Partial<TaskState>): void
  list(): TaskState[]
  get(id: string): TaskState | undefined
}
```

