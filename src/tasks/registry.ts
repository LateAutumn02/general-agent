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
      createdAt: now,
      updatedAt: now,
    }
    this.tasks.set(task.id, task)
    return task
  }

  update(id: string, patch: Partial<Omit<TaskState, 'id' | 'createdAt'>>) {
    const current = this.tasks.get(id)
    if (!current) return undefined
    const next = { ...current, ...patch, updatedAt: Date.now() }
    this.tasks.set(id, next)
    return next
  }

  get(id: string) {
    return this.tasks.get(id)
  }

  list() {
    return [...this.tasks.values()].sort((a, b) => b.updatedAt - a.updatedAt)
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
