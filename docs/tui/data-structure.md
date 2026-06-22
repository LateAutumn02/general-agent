# TUI 数据结构

> 最后更新：2026-06-22

## TuiState

```ts
type TuiState = {
  transcript: TranscriptItem[]
  streamingText: string
  input: PromptInputState
  footer: FooterState
  permission?: PermissionRequest
  taskBoard?: TaskBoardState
  /** 蜂群可视化状态 */
  swarmView?: SwarmViewState
}
```

## PromptInputState

```ts
type PromptInputState = {
  value: string
  mode: 'prompt' | 'bash' | 'command' | 'file'
  cursorOffset: number
  placeholder: string
  historyIndex?: number
  /** 当前输入的 agent 上下文 */
  agentContext?: AgentContextBanner
}
```

## TranscriptItem

```ts
type TranscriptItem =
  | { type: 'user'; text: string; messageId: string }
  | { type: 'assistant'; text: string; messageId: string }
  | { type: 'tool_summary'; callId: string; text: string; status: ToolStatus }
  | { type: 'error'; text: string }
  | { type: 'separator' }
  /** Agent 工具调用的分组进度 */
  | { type: 'agent_progress'; agents: AgentProgressLine[]; status: 'running' | 'completed' }
  /** 队友消息 */
  | { type: 'teammate_message'; from: string; color: string; messageType: TeammateMessageType; summary?: string; content: string }
```

## AgentProgressLine

```ts
type AgentProgressLine = {
  /** agent 类型名称 */
  agentType: string
  /** 是否为 teammate（显示 @name） */
  isTeammateSpawn?: boolean
  teammateName?: string
  teammateColor?: string
  description: string
  status: 'initializing' | 'running' | 'completed' | 'failed'
  lastToolName?: string
  lastToolSummary?: string
  toolUseCount: number
  tokenCount: number
  durationMs: number
  isBackground: boolean
}
```

## TeammateMessageType

```ts
type TeammateMessageType =
  | 'text'
  | 'task_completed'
  | 'task_assignment'
  | 'shutdown_request'
  | 'shutdown_response'
  | 'idle_notification'
  | 'plan_approval'
```

## SwarmViewState

```ts
type SwarmViewState = {
  /** Spinner 树中的 teammate 列表 */
  teammates: TeammateSpinnerLine[]
  /** Leader 当前动词 */
  leaderVerb?: string
  /** 展开模式 */
  expandedView: 'collapsed' | 'teammates' | 'tasks'
  /** 选中的 teammate 索引 */
  selectedTeammateIndex: number
}
```

## TeammateSpinnerLine

```ts
type TeammateSpinnerLine = {
  name: string
  color: string
  status: 'idle' | 'running' | 'stopping' | 'awaiting_approval'
  verb?: string
  activityText?: string
  toolUseCount: number
  tokenCount: number
  idleDurationMs?: number
  messagePreview?: string[]
}
```

## AgentContextBanner

```ts
type AgentContextBanner = {
  /** 当前输入上下文 */
  agentName: string
  color: string
  isMain: boolean
}
```

## FooterState

```ts
type FooterState = {
  model: string
  cwd: string
  permissionMode: PermissionMode
  taskCounts: { awaiting: number; running: number; completed: number }
  /** Agent pills（蜂群模式） */
  agentPills: AgentPill[]
  /** 选中的 pill 索引 */
  selectedPillIndex?: number
}
```

## AgentPill

```ts
type AgentPill = {
  name: string
  color: string
  isMain: boolean
  isSelected: boolean
}
```

## TaskItem（增强版）

```ts
type TaskItem = {
  id: number
  status: 'pending' | 'in_progress' | 'completed' | 'blocked'
  subject: string
  owner?: string
  ownerActivity?: string
  blockedBy?: number[]
  createdAt: number
}
```

## TaskBoardState

```ts
type TaskBoardState = {
  tasks: TaskItem[]
  summary: { total: number; done: number; inProgress: number; open: number }
}
```
