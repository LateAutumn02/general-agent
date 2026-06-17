# 工具系统数据结构

> 最后更新：2026-06-17

## ToolDefinition

```ts
type ToolDefinition<TInput = unknown> = {
  name: string
  description: string
  inputSchema: JsonSchema
  readOnly: boolean
  checkPermission(input: TInput, context: ToolContext): Promise<PermissionCheck>
  execute(input: TInput, context: ToolContext): Promise<ToolResult>
  summarize(input: TInput, result?: ToolResult): string
}
```

## ToolContext

```ts
type ToolContext = {
  cwd: string
  signal: AbortSignal
  sessionId: string
  taskRegistry: TaskRegistry
  emit: (event: RuntimeEvent) => void
}
```

## ToolCall

```ts
type ToolCall = {
  id: string
  name: string
  input: unknown
  status: ToolStatus
  createdAt: number
}
```

## ToolResult

```ts
type ToolResult = {
  callId: string
  ok: boolean
  content: MessageContent[]
  display?: ToolDisplay
  error?: string
}
```

## ToolStatus

```ts
type ToolStatus = 'pending' | 'awaiting_permission' | 'running' | 'completed' | 'failed' | 'cancelled'
```

