export type TaskStatus = 'awaiting_input' | 'running' | 'completed' | 'failed' | 'cancelled'

export type TaskKind = 'agent' | 'shell' | 'manual'

export type TaskState = {
  id: string
  type: TaskKind
  status: TaskStatus
  title: string
  activity: string
  createdAt: number
  updatedAt: number
}

export type CreateTaskInput = {
  type: TaskKind
  title: string
  activity?: string
  status?: TaskStatus
}
