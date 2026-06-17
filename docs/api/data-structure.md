# 模型 API 数据结构

> 最后更新：2026-06-17

## ModelClient

```ts
type ModelClient = {
  stream(request: ModelRequest, signal: AbortSignal): AsyncIterable<ModelStreamEvent>
}
```

## ModelRequest

```ts
type ModelRequest = {
  model: string
  system: string
  messages: ChatMessage[]
  tools: ToolDefinition[]
  maxTokens?: number
  temperature?: number
}
```

## ModelStreamEvent

```ts
type ModelStreamEvent =
  | { type: 'text_delta'; text: string }
  | { type: 'tool_use'; call: ToolCall }
  | { type: 'message_done'; message: ChatMessage }
  | { type: 'usage'; inputTokens: number; outputTokens: number }
```

## ModelProvider

```ts
type ModelProvider = 'anthropic-compatible' | 'openai-compatible' | 'azure-openai' | 'custom'
```

