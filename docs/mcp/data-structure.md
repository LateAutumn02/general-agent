# MCP 数据结构

> 最后更新：2026-06-17

## McpServerConfig

```ts
type McpServerConfig = {
  name: string
  command: string
  args: string[]
  env?: Record<string, string>
  cwd?: string
}
```

## McpConnection

```ts
type McpConnection = {
  name: string
  status: 'starting' | 'ready' | 'failed' | 'closed'
  tools: ToolDefinition[]
  close(): Promise<void>
}
```

## McpToolName

```ts
type McpToolName = `mcp__${string}__${string}`
```

