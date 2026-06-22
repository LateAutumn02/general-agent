# Swarm 蜂群协作数据结构

> 最后更新：2026-06-22 | 参考：reference/cc-haha/src/tools/AgentTool, TeamCreateTool, SendMessageTool, utils/teammateMailbox, utils/swarm/

## 核心类型概览

```
AgentTool.input  → Agent 调用参数（description, prompt, subagent_type, name, team_name）
TeamCreate.input → 建队参数
SendMessage.input → 消息投递参数
TeamFile         → 团队持久化文件结构
MailboxMessage   → 信箱消息结构
AgentDefinition  → 可用 agent 类型定义
```

---

## Agent Tool

### 输入 Schema (fullInputSchema)

```ts
type AgentInput = {
  /** 3-5 词的简短任务描述 */
  description: string

  /** 给 agent 的完整任务指令 */
  prompt: string

  /** 使用的 agent 类型（omit = general-purpose / fork 自身） */
  subagent_type?: string

  /** 模型覆盖（sonnet | opus | haiku） */
  model?: string

  /** 后台运行（完成后自动通知） */
  run_in_background?: boolean

  /** 隔离模式（worktree | remote） */
  isolation?: 'worktree' | 'remote'

  // ---- 多 agent 参数（teammate spawn） ----
  /** agent 名称，用于 SendMessage({to: name}) 寻址 */
  name?: string

  /** 团队名。省略则使用当前 teamContext */
  team_name?: string

  /** 权限模式（如 "plan" 要求审批后才能写代码） */
  mode?: PermissionMode
}
```

### 输出 Schema

```ts
type AgentResult = {
  /** agent 的最终文本响应 */
  result: string

  /** 转录输出文件路径（fork 模式） */
  output_file?: string

  /** 消耗的 tokens */
  usage?: TokenUsage

  /** agent ID（用于后续 SendMessage 续接） */
  agentId?: string

  /** worktree 路径（如果用 worktree 隔离） */
  worktreePath?: string
}
```

### Agent Tool Prompt 结构

```ts
getPrompt(agentDefinitions: AgentDefinition[], isCoordinator?: boolean): string
```

返回的 prompt 包含以下 section：
1. **Shared** — 工具概述 + agent 类型列表
2. **When NOT to use** — 什么情况下不应该用 Agent（读文件用 Read、搜索用 Glob）
3. **Usage notes** — 并发、前后台、worktree、trust
4. **When to fork** — fork 自身 vs spawn 新 agent
5. **Writing the prompt** — 如何给 agent 写有效指令
6. **Examples** — fork 示例 + 传统 agent 示例

Coordinator 模式只返回 Shared section（其余在 coordinator 系统提示词中）。

---

## TeamCreate Tool

### 输入 Schema

```ts
type TeamCreateInput = {
  /** 团队名（如已存在则自动生成唯一名） */
  team_name: string

  /** 团队描述/目标 */
  description?: string

  /** team-lead 的 agent 类型（默认 "team-lead"） */
  agent_type?: string
}
```

### 输出 Schema

```ts
type TeamCreateOutput = {
  team_name: string
  team_file_path: string        // ~/.claude/teams/{name}/config.json
  lead_agent_id: string         // team-lead@{team_name}
}
```

### 触发条件（prompt 描述）

LLM 应在以下情况主动调用 TeamCreate：
- 用户明确提到"团队"、"swarm"、"一组 agent"
- 任务复杂到需要并行多个 agent（全栈功能、重构+测试、多步骤项目）
- 不确定是否需要团队时，倾向于建队

---

## TeamFile

持久化在 `~/.claude/teams/{team_name}/config.json`：

```ts
type TeamFile = {
  /** 团队名 */
  name: string

  /** 团队描述 */
  description?: string

  /** 创建时间 */
  createdAt: number

  /** team-lead 的 agent ID */
  leadAgentId: string

  /** team-lead 的 session ID */
  leadSessionId: string

  /** 团队成员列表 */
  members: TeamMember[]
}
```

```ts
type TeamMember = {
  /** 唯一标识符 */
  agentId: string

  /** 人类可读名称（用于 SendMessage to 字段） */
  name: string

  /** agent 类型/角色 */
  agentType: string

  /** 使用的模型覆盖 */
  model?: string

  /** 加入时间 */
  joinedAt: number

  /** tmux pane ID（tmux 模式） */
  tmuxPaneId: string

  /** 工作目录 */
  cwd: string

  /** 订阅的主题列表（pub/sub） */
  subscriptions: string[]
}
```

---

## SendMessage Tool

### 输入 Schema

```ts
type SendMessageInput = {
  /** 接收方：teammate name | "*" 广播 | "uds:<path>" | "bridge:<id>" */
  to: string

  /** 5-10 词的简短预览 */
  summary?: string

  /** 消息内容（纯文本 或 结构化协议消息） */
  message: string | StructuredMessage
}
```

### 结构化协议消息（StructuredMessage）

```ts
type StructuredMessage =
  | { type: 'shutdown_request';  reason?: string }
  | { type: 'shutdown_response'; request_id: string; approve: boolean; reason?: string }
  | { type: 'plan_approval_response'; request_id: string; approve: boolean; feedback?: string }
```

### 消息路由（MessageRouting）

```ts
type MessageRouting = {
  sender: string            // 发送者名称
  senderColor?: string      // 发送者颜色
  target: string            // 目标名称
  targetColor?: string      // 目标颜色
  summary?: string          // 消息摘要
  content?: string          // 消息内容
}
```

---

## Mailbox（文件信箱）

### 信箱消息

存储在 `~/.claude/teams/{team}/inboxes/{agent_name}.json`：

```ts
type MailboxMessage = {
  /** 发送者名称 */
  from: string

  /** 消息文本 */
  text: string

  /** ISO 时间戳 */
  timestamp: string

  /** 是否已读 */
  read: boolean

  /** 发送者颜色 */
  color?: string

  /** 5-10 词摘要 */
  summary?: string
}
```

### 信箱操作

```ts
type MailboxOps = {
  /** 获取信箱路径 */
  getInboxPath(agentName: string, teamName?: string): string

  /** 读取所有消息 */
  getInboxMessages(agentName: string, teamName?: string): Promise<MailboxMessage[]>

  /** 写入消息到目标信箱 */
  writeToMailbox(
    teamName: string,
    targetAgentName: string,
    msg: Omit<MailboxMessage, 'read'>
  ): Promise<void>

  /** 标记消息已读 */
  markAsRead(agentName: string, messageIndex: number): Promise<void>

  /** 清空信箱 */
  clearMailbox(agentName: string): Promise<void>
}
```

写入使用 `lockfile` 库保证并发安全（最多重试 10 次，指数退避）。

---

## AgentDefinition

从 `.claude/agents/` 目录加载的自定义 agent 定义：

```ts
type AgentDefinition = {
  /** agent 类型标识符（用于 subagent_type 参数） */
  agentType: string

  /** 人类可读名称 */
  name: string

  /** 一句话描述能力 */
  description: string

  /** 何时使用此 agent */
  whenToUse: string

  /** 工具允许列表（undefined = 全部） */
  tools?: string[]

  /** 工具禁止列表 */
  disallowedTools?: string[]

  /** 默认模型覆盖 */
  model?: string
}
```

### 内置 Agent 类型

```ts
const BUILTIN_AGENTS = {
  'general-purpose': {
    agentType: 'general-purpose',
    whenToUse: 'Catch-all for any task that does not fit a more specific agent',
    tools: undefined,  // all tools except disallowed
  },
  'Explore': {
    agentType: 'Explore',
    whenToUse: 'Read-only search agent for broad fan-out searches',
    tools: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  },
  'Plan': {
    agentType: 'Plan',
    whenToUse: 'Software architect agent for designing implementation plans',
    tools: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  },
  // ... 更多
}
```

---

## Coordinator 模式

```ts
type CoordinatorModeApi = {
  /** 当前是否为 coordinator 模式 */
  isCoordinatorMode(): boolean

  /** 匹配会话存储的 mode，必要时切换 env var */
  matchSessionMode(sessionMode?: 'coordinator' | 'normal'): string | undefined
}
```

Coordinator 工具集：
```ts
COORDINATOR_ALLOWED_TOOLS = ['Agent', 'TaskStop', 'SendMessage', 'SyntheticOutput']
```

---

## Teammate 身份

```ts
type TeammateIdentity = {
  getAgentId(): string | undefined
  getAgentName(): string | undefined
  getTeamName(): string | undefined
  getTeammateColor(): string | undefined
  isTeammate(): boolean
  isTeamLead(): boolean
}
```

身份解析优先级：
1. `AsyncLocalStorage`（in-process 模式）
2. `dynamicTeamContext`（tmux 模式）
3. 环境变量（`CLAUDE_CODE_AGENT_ID` 等）

---

## Swarm Backend

```ts
type BackendType = 'tmux' | 'iterm2' | 'in-process'

type PaneBackend = {
  type: BackendType

  /** 创建新 pane */
  createPane(options: PaneOptions): Promise<PaneInfo>

  /** 销毁 pane */
  killPane(paneId: string): Promise<void>

  /** 获取 pane 状态 */
  getPaneStatus(paneId: string): Promise<PaneStatus>
}

type TeammateExecutor = {
  /** 在 pane 中执行 teammate */
  execute(teammate: TeamMember, backend: PaneBackend): Promise<void>
}
```

---

## 工具权限矩阵

```ts
/** 所有子 agent 禁止使用的工具 */
const ALL_AGENT_DISALLOWED_TOOLS = [
  'Agent',        // 防止递归生成 agent
  'AskUserQuestion',
  'TaskStop',
  'ExitPlanMode',
  'EnterPlanMode',
]

/** 异步 worker agent 可用工具 */
const ASYNC_AGENT_ALLOWED_TOOLS = [
  'Bash', 'Read', 'Edit', 'Write',
  'Grep', 'Glob', 'WebSearch', 'WebFetch',
  'TodoWrite', 'Skill',
]

/** Coordinator 模式可用工具 */
const COORDINATOR_MODE_ALLOWED_TOOLS = [
  'Agent', 'TaskStop', 'SendMessage', 'SyntheticOutput',
]
```

---

## 可视化相关类型

### AgentProgressLine

```ts
type AgentProgressLine = {
  /** agent 类型名称 */
  agentType: string

  /** 是否为 teammate spawn（显示 @name 而非类型名） */
  isTeammateSpawn?: boolean

  /** teammate 名称 */
  teammateName?: string

  /** teammate 颜色 */
  teammateColor?: string

  /** 任务描述 */
  description: string

  /** agent 状态 */
  status: 'initializing' | 'running' | 'completed' | 'failed'

  /** 最后执行的工具名 */
  lastToolName?: string

  /** 最后工具的参数摘要 */
  lastToolSummary?: string

  /** tool 使用次数 */
  toolUseCount: number

  /** token 使用量 */
  tokenCount: number

  /** 执行耗时 (ms) */
  durationMs: number

  /** 是否为后台运行 */
  isBackground: boolean
}
```

### TeammateSpinnerLine

```ts
type TeammateSpinnerLine = {
  /** agent 名称（如 "researcher"） */
  name: string

  /** 分配的颜色 */
  color: string

  /** 当前状态 */
  status: 'idle' | 'running' | 'stopping' | 'awaiting_approval'

  /** 状态动词（如 "Searching"） */
  verb?: string

  /** 活动描述文本 */
  activityText?: string

  /** tool 使用计数 */
  toolUseCount: number

  /** token 计数 */
  tokenCount: number

  /** 空闲时长 (ms) */
  idleDurationMs?: number

  /** 消息预览（最近 3 行对话） */
  messagePreview?: string[]
}
```

### TeammateMessage（聊天内显示的消息）

```ts
type TeammateMessage = {
  /** 发送方名称 */
  from: string

  /** 发送方颜色 */
  color: string

  /** 消息类型 */
  type: 'text' | 'task_completed' | 'task_assignment'
       | 'shutdown_request' | 'shutdown_response'
       | 'idle_notification' | 'plan_approval'

  /** 消息摘要 */
  summary?: string

  /** 消息内容 */
  content: string

  /** 关联的任务 ID */
  taskId?: number

  /** 关联的任务标题 */
  taskSubject?: string
}
```

### TaskItem（增强版任务条目）

```ts
type TaskItem = {
  id: number
  status: 'pending' | 'in_progress' | 'completed' | 'blocked'
  subject: string
  owner?: string          // agent 名称
  ownerActivity?: string   // owner 当前正在做什么
  blockedBy?: number[]     // 阻塞此任务的任务 ID 列表
  createdAt: number
  completedAt?: number
}
```

### FooterAgentPill

```ts
type AgentPill = {
  name: string
  color: string
  isMain: boolean
  isSelected: boolean
}
```

---

## 项目存储路径

```
~/.claude/
  teams/
    {team_name}/
      config.json          ← TeamFile（成员列表、元数据）
      inboxes/
        {agent_name}.json  ← 信箱（MailboxMessage[]）
  agents/
    {name}.md              ← 自定义 AgentDefinition
  tasks/
    {team_name}/           ← 团队共享任务列表
```
