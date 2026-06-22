import type { CreateTaskInput, TaskState } from './types.js'

export class TaskRegistry {
  private readonly tasks = new Map<string, TaskState>()

  create(input: CreateTaskInput) {
    const now = Date.now()
    const task: TaskState = {
      id: crypto.randomUUID(),
      type: input.type,
      status: input.status ?? 'running',
      title: input.title,
      activity: input.activity ?? 'Starting',
      messages: input.messages ?? [],
      output: input.output,
      createdAt: now,
      updatedAt: now,
    }
    this.tasks.set(task.id, task)
    return task
  }

  update(id: string, patch: Partial<Omit<TaskState, 'id' | 'createdAt'>>) {
    const current = this.tasks.get(id)
    if (!current) return undefined
    const now = Date.now()
    const terminal = patch.status === 'completed'
      || patch.status === 'failed'
      || patch.status === 'cancelled'
    const next = {
      ...current,
      ...patch,
      completedAt: terminal ? patch.completedAt ?? current.completedAt ?? now : patch.completedAt ?? current.completedAt,
      updatedAt: now,
    }
    this.tasks.set(id, next)
    return next
  }

  get(id: string) {
    return this.tasks.get(id)
  }

  list() {
    return [...this.tasks.values()].sort((a, b) => b.updatedAt - a.updatedAt)
  }

  delete(id: string) {
    return this.tasks.delete(id)
  }

  appendMessage(id: string, message: TaskState['messages'][number]) {
    const current = this.tasks.get(id)
    if (!current) return undefined
    return this.update(id, { messages: [...current.messages, message] })
  }

  counts() {
    const tasks = this.list()
    return {
      awaiting: tasks.filter(task => task.status === 'awaiting_input').length,
      running: tasks.filter(task => task.status === 'running').length,
      completed: tasks.filter(task => task.status === 'completed').length,
    }
  }
}
