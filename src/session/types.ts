import type { RuntimeEvent } from '../runtime/events.js'
import type { PermissionDecision } from '../permissions/types.js'
import type { TaskItem } from '../tui/types.js'

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  text: string
  createdAt: number
}

export type SessionRecord = {
  id: string
  title: string
  cwd: string
  model: string
  createdAt: number
  updatedAt: number
  messageCount: number
}

export type SessionEvent =
  | { type: 'message'; message: ChatMessage }
  | { type: 'runtime_event'; event: RuntimeEvent }
  | { type: 'permission_decision'; requestId: string; decision: PermissionDecision }
  | { type: 'task_state'; task: TaskItem }
  | { type: 'metadata'; patch: Partial<SessionRecord> }

export type CreateSessionInput = {
  cwd: string
  model: string
  title?: string
}

export type LoadedSession = {
  record: SessionRecord
  events: SessionEvent[]
  messages: ChatMessage[]
  tasks: TaskItem[]
}
