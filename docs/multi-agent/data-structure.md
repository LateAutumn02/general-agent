# 多 Agent 数据结构

> 最后更新：2026-06-17

## AgentProfile

```ts
type AgentProfile = {
  name: string
  description: string
  systemPrompt: string
  allowedTools: string[]
}
```

## AgentTask

```ts
type AgentTask = TaskState & {
  type: 'agent'
  profile: AgentProfile
  parentSessionId: string
  resultSummary?: string
}
```

## AgentToolInput

```ts
type AgentToolInput = {
  description: string
  prompt: string
  profile?: string
  allowedTools?: string[]
}
```

