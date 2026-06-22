export type PromptMode = 'prompt' | 'bash' | 'command' | 'file'

export type ToolStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type PermissionRequest = {
  id: string
  toolName: string
  command: string
  reason: string
  prefixRule: string
}

export type PermissionDecision =
  | { type: 'allow'; remember: false }
  | { type: 'allow'; remember: true }
  | { type: 'deny'; reason?: string }

export type TaskStatus = 'awaiting_input' | 'running' | 'completed'

export type TaskItem = {
  id: string
  status: TaskStatus
  title: string
  activity: string
  messages: number
  output?: string
  age: string
}

// ---- Swarm / Multi-Agent Visualization Types ----

/** 队友消息类型（在 transcript 中渲染） */
export type TeammateMessageType =
  | 'text'
  | 'task_completed'
  | 'task_assignment'
  | 'shutdown_request'
  | 'shutdown_response'
  | 'idle_notification'

/** Agent 执行进度（树形摘要） */
export type AgentProgressLine = {
  agentId: string
  agentType: string
  description: string
  status: 'initializing' | 'running' | 'completed' | 'failed'
  toolUseCount: number
  tokenCount: number
  durationMs: number
  isBackground: boolean
}

/** Footer 中的 agent 标签 */
export type AgentPill = {
  name: string
  color: 'yellow' | 'green' | 'cyan' | 'magenta' | 'blue' | 'red'
  isMain: boolean
  isSelected: boolean
}

export type TranscriptItem =
  | { type: 'user'; id: string; text: string }
  | { type: 'assistant'; id: string; text: string }
  | { type: 'tool_summary'; id: string; text: string; status: ToolStatus }
  | { type: 'error'; id: string; text: string }
  /** Agent 分组进度（多 agent 并行时） */
  | { type: 'agent_progress'; id: string; agents: AgentProgressLine[]; status: 'running' | 'completed' }
  /** 队友消息 */
  | { type: 'teammate_message'; id: string; from: string; color: string; messageType: TeammateMessageType; summary: string; content: string }
  /** 折叠的工具调用组（同类合并） */
  | { type: 'tool_group'; id: string; toolName: string; count: number; summary: string; status: ToolStatus }
