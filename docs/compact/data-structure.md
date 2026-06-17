# 上下文压缩数据结构

> 最后更新：2026-06-17

## CompactState

```ts
type CompactState = {
  lastCompactAt?: number
  summarizedUntilMessageId?: string
  estimatedTokens: number
  autoCompactCount: number
}
```

## CompactRequest

```ts
type CompactRequest = {
  messages: ChatMessage[]
  reason: 'manual' | 'token_budget' | 'recovery'
  preserveMessageCount: number
}
```

## CompactResult

```ts
type CompactResult = {
  summaryMessage: ChatMessage
  removedMessageIds: string[]
  beforeTokens: number
  afterTokens: number
}
```

