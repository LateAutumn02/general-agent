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

export type TranscriptItem =
  | { type: 'user'; id: string; text: string }
  | { type: 'assistant'; id: string; text: string }
  | { type: 'tool_summary'; id: string; text: string; status: ToolStatus }
  | { type: 'error'; id: string; text: string }
