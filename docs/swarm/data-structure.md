# Swarm 数据结构

> 最后更新：2026-06-22
> 代码依据：`src/swarm/teamConfig.ts`、`src/swarm/mailbox.ts`、`src/tools/tools/*.ts`、`src/tasks/types.ts`、`src/session/types.ts`

## 存储路径

当前 swarm 的持久化数据放在项目目录下：

```text
.general-agent/
  teams/
    {team}/
      config.json
      inboxes/
        {agent}.json
  sessions/
    {sessionId}.jsonl
```

注意：这里使用的是 `.general-agent`。

## TeamCreate 输入

来源：`src/tools/tools/teamCreate.ts`

```ts
type TeamCreateInput = {
  team_name: string
  description?: string
}
```

当前没有 `agent_type`、`model`、`backend` 等字段。

## TeamConfig

来源：`src/swarm/teamConfig.ts`

```ts
type TeamConfig = {
  name: string
  description?: string
  createdAt: number
  leadAgentId: string
  members: TeamMember[]
}
```

```ts
type TeamMember = {
  agentId: string
  name: string
  agentType: string
  joinedAt: number
  cwd: string
}
```

示例：

```json
{
  "name": "swarm-test-1",
  "description": "Verify inter-agent messaging",
  "createdAt": 1781765599294,
  "leadAgentId": "lead@swarm-test-1",
  "members": [
    {
      "agentId": "lead@swarm-test-1",
      "name": "main",
      "agentType": "general-purpose",
      "joinedAt": 1781765599294,
      "cwd": "C:\\Users\\why7052\\Desktop\\general-agent"
    },
    {
      "agentId": "agent-a@swarm-test-1",
      "name": "agent-a",
      "agentType": "general-purpose",
      "joinedAt": 1781765600000,
      "cwd": "C:\\Users\\why7052\\Desktop\\general-agent"
    }
  ]
}
```

当前没有这些字段：

- `leadSessionId`
- `tmuxPaneId`
- `subscriptions`
- `model`
- `color`
- `status`
- `lastSeenAt`

## Agent 输入

来源：`src/tools/tools/agent.ts`

```ts
type AgentInput = {
  description: string
  prompt: string
  subagent_type?: string
  name?: string
  team_name?: string
}
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| `description` | 短任务描述，用于审批和 UI 标题 |
| `prompt` | 给子 agent 的完整任务 |
| `subagent_type` | 子 agent 类型，默认 `general-purpose` |
| `name` | agent 名称；有名称才会注册到 team，也才能被 `SendMessage` 寻址 |
| `team_name` | team 名称，默认 `default` |

当前没有这些字段：

- `model`
- `run_in_background`
- `isolation`
- `mode`
- `output_file`
- `worktreePath`

## SendMessage 输入

来源：`src/tools/tools/sendMessage.ts`

```ts
type SendMessageInput = {
  to: string
  team_name?: string
  summary?: string
  message: string
}
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| `to` | 接收方 agent 名称；`"*"` 表示广播 |
| `team_name` | team 名称；默认使用当前 agent 的 team，再退回 `default` |
| `summary` | 简短摘要，写入信箱 |
| `message` | 消息正文，目前只能是字符串 |

当前不支持：

- `uds:<path>`
- `bridge:<id>`
- 结构化 message 对象
- shutdown / plan approval / permission response 协议消息

## MailboxMessage

来源：`src/swarm/mailbox.ts`

```ts
type MailboxMessage = {
  from: string
  text: string
  timestamp: string
  read: boolean
  summary?: string
}
```

信箱文件路径：

```text
.general-agent/teams/{team}/inboxes/{agent}.json
```

示例：

```json
[
  {
    "from": "agent-a",
    "text": "bridge",
    "summary": "word chosen",
    "timestamp": "2026-06-22T10:30:00.000Z",
    "read": false
  }
]
```

读取规则：

- `readMailbox` 读取全部消息。
- `readUnreadMessages` 只返回 `read: false` 的消息。
- `readUnreadMessages` 返回后会把这些消息标记为已读。
- `writeToMailbox` 追加写入消息。
- `broadcastToTeam` 给团队中除发送者以外的成员逐个写入信箱。

当前写入没有文件锁和重试机制，所以并发安全还不完整。

## 子 agent 运行状态

子 agent 当前没有单独的持久化状态结构。`runSubAgent` 会临时创建一个 `AgentState`：

```ts
type AgentState = {
  sessionId: string
  messages: ChatMessage[]
  turnCount: number
  cwd: string
  model: string
}
```

子 agent 的 `sessionId` 格式为：

```text
{mainSessionId}:{agentName}
```

但当前没有把子 agent transcript 写入独立 jsonl，也没有在 `/resume` 中恢复它。

## ChatMessage 工具协议

来源：`src/session/types.ts`

当前消息结构支持 OpenAI-compatible 工具调用：

```ts
type ChatMessage = {
  id: string
  role: 'system' | 'user' | 'assistant' | 'tool'
  text: string
  createdAt: number
  toolCalls?: Array<{
    id: string
    name: string
    input: unknown
  }>
  toolCallId?: string
  toolName?: string
}
```

关键点：

- assistant 发起工具调用时，`toolCalls` 保存在 assistant message 上。
- 工具结果使用 `role: "tool"`。
- `toolCallId` 对应原工具调用 id。

## 工具注册表

来源：`src/tools/registry.ts`

主 agent 工具：

```text
Bash
Read
Write
Edit
Glob
Grep
Agent
SendMessage
TeamCreate
PowerShell   // Windows only
```

`Explore` 子 agent 工具：

```text
Read
Glob
Grep
SendMessage
```

默认子 agent 工具：

```text
Bash
Read
Write
Edit
Glob
Grep
SendMessage
PowerShell   // Windows only
```

所有子 agent 当前都不能使用 `Agent` 和 `TeamCreate`。

## TUI TaskState

来源：`src/tasks/types.ts`

```ts
type TaskStatus =
  | 'awaiting_input'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

type TaskKind =
  | 'agent'
  | 'shell'
  | 'manual'

type TaskState = {
  id: string
  type: TaskKind
  status: TaskStatus
  title: string
  activity: string
  messages: ChatMessage[]
  output?: string
  createdAt: number
  updatedAt: number
  completedAt?: number
}
```

TUI 对 `Agent` 工具调用的映射：

| Runtime event | Task 行为 |
| --- | --- |
| `tool_call_started` + `Agent` | 创建 `type: "agent"` task |
| `tool_call_finished` + Agent ok | 标记 `completed`，追加结果消息，写入 `completedAt` |
| `tool_call_finished` + Agent failed | 标记 `failed`，追加错误输出，写入 `completedAt` |

当前 TaskBoard 只显示顶层 Agent 工具调用，不显示子 agent 内部的每一次工具调用。

## 未实现的数据结构

这些结构在参考项目或早期设计里出现过，但当前代码里没有正式落地：

| 结构 | 当前状态 |
| --- | --- |
| `StructuredMessage` | 未实现，`SendMessage.message` 目前是字符串 |
| `CoordinatorModeApi` | 未实现 |
| `PaneBackend` / tmux backend | 未实现 |
| `TeammateIdentity` 环境变量解析 | 未实现 |
| `TaskCreate` / `TaskUpdate` 共享任务数据 | 未实现 |
| `AgentProgressLine` 实时内部进度 | 部分 UI 类型存在，但 runtime 只接顶层 Agent 结果 |
| 子 agent transcript jsonl | 未实现 |
| mailbox 文件锁 | 未实现 |
| permission bridge | 未实现 |
