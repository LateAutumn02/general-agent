# Agent 核心循环数据结构

> 最后更新：2026-06-17

## AgentState

```ts
type AgentState = {
  sessionId: string
  messages: ChatMessage[]
  turnCount: number
  cwd: string
  model: string
  abortController?: AbortController
  compactState: CompactState
  pendingToolCalls: ToolCall[]
}
```

## TurnRequest

```ts
type TurnRequest = {
  id: string
  mode: 'prompt' | 'bash' | 'command'
  text: string
  createdAt: number
  attachments: Attachment[]
}
```

## ChatMessage

```ts
type ChatMessage = {
  id: string
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: MessageContent[]
  createdAt: number
  meta?: Record<string, unknown>
}
```

## MessageContent

```ts
type MessageContent =
  | { type: 'text'; text: string }
  | { type: 'tool_use'; call: ToolCall }
  | { type: 'tool_result'; callId: string; result: ToolResult }
  | { type: 'attachment'; attachment: Attachment }
```

