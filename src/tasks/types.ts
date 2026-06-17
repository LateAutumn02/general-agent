import type { ChatMessage } from '../session/types.js'

export type TaskStatus = 'awaiting_input' | 'running' | 'completed' | 'failed' | 'cancelled'

export type TaskKind = 'agent' | 'shell' | 'manual'

export type TaskState = {
  id: string
  type: TaskKind
  status: TaskStatus
  title: string
  activity: string
  messages: ChatMessage[]
  output?: string
  createdAt: number
  updatedAt: number
}

export type CreateTaskInput = {
  type: TaskKind
  title: string
  activity?: string
  status?: TaskStatus
  messages?: ChatMessage[]
  output?: string
}
