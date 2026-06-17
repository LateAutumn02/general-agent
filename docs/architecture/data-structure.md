# 系统架构数据结构

> 最后更新：2026-06-17

## AppContext

```ts
type AppContext = {
  cwd: string
  config: RuntimeConfig
  modelClient: ModelClient
  toolRegistry: ToolRegistry
  permissionController: PermissionController
  sessionStore: SessionStore
  taskRegistry: TaskRegistry
  eventBus: RuntimeEventBus
}
```

## RuntimeEvent

```ts
type RuntimeEvent =
  | { type: 'user_message'; message: ChatMessage }
  | { type: 'assistant_delta'; text: string; messageId: string }
  | { type: 'assistant_done'; message: ChatMessage }
  | { type: 'tool_call_started'; call: ToolCall }
  | { type: 'tool_call_finished'; callId: string; result: ToolResult }
  | { type: 'permission_request'; request: PermissionRequest }
  | { type: 'permission_resolved'; requestId: string; decision: PermissionDecision }
  | { type: 'task_updated'; task: TaskState }
  | { type: 'error'; error: RuntimeError }
```

## RuntimeMode

```ts
type RuntimeMode = 'tui' | 'print' | 'recovery'
```

## 目录约定

```text
src/cli          # 进程入口
src/tui          # Ink UI
src/agent        # Agent loop
src/tools        # 工具实现
src/session      # 会话存储
src/tasks        # 后台任务
src/permissions  # 权限策略
```

